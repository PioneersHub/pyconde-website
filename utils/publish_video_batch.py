"""Turn a 2026 video drop into a publish event, not a silent asset upload.

Wraps the existing pieces into one command so a rolling recording release
becomes a deliberate recrawl + AI-ingest event:

  1. Sync the videos for one thematic batch (scoped by --codes read from
     `databags/recordings.yaml` `batches.<year>.<batch>.codes`) into the
     talk pages via `utils/sync_recordings.py`.
  2. Rebuild the site (`make build`) so the segmented sitemaps, the
     `<lastmod>` bumps (see templates/macros/sitemap-url.html), the
     Pagefind index, and `/llms.txt` + `/llms-full-archive.txt` regenerate
     from the freshly-enriched talk pages.
  3. Ping Google and Bing with the sitemap index so the recrawl is
     triggered without waiting for their own cadence.

The batch codes are the only thing the operator edits in recordings.yaml;
everything else is derived. Run as:

    make publish-video-batch YEAR=2026 BATCH=llm-agents

or directly:

    python utils/publish_video_batch.py --year 2026 --batch llm-agents

Flags:
  --no-build    skip the `make build` step (use when the build is run
                separately, e.g. in CI).
  --no-ping     skip the sitemap ping step (e.g. for local dry runs).
  --dry-run     pass through to sync_recordings; no files written, no
                build, no ping.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.parse
from pathlib import Path

import httpx
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDINGS_CONFIG = REPO_ROOT / "databags" / "recordings.yaml"
BRANDING_CONFIG = REPO_ROOT / "databags" / "branding.yaml"

PING_ENDPOINTS = {
    "google": "https://www.google.com/ping?sitemap={sitemap}",
    "bing": "https://www.bing.com/ping?sitemap={sitemap}",
}


def load_recordings() -> dict:
    with RECORDINGS_CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def canonical_host() -> str:
    with BRANDING_CONFIG.open(encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("canonical_host", "").rstrip("/")


def resolve_batch(cfg: dict, year: str, batch: str) -> dict:
    batches = (cfg.get("batches") or {}).get(str(year)) or {}
    if batch not in batches:
        available = ", ".join(sorted(batches)) or "<none defined>"
        raise SystemExit(
            f"Batch '{batch}' not found for year {year} in databags/recordings.yaml. "
            f"Available: {available}"
        )
    return batches[batch]


def run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def sync_batch(year: str, codes: list[str], dry_run: bool) -> None:
    if not codes:
        raise SystemExit("Batch has no codes; nothing to sync.")
    cmd = [
        sys.executable,
        str(REPO_ROOT / "utils" / "sync_recordings.py"),
        "--year",
        year,
        "--codes",
        ",".join(codes),
    ]
    if dry_run:
        cmd.append("--dry-run")
    run(cmd)


def build_site() -> None:
    make = Path("make")
    # Prefer `make build` if a Makefile is present; fall back to uv.
    if (REPO_ROOT / "Makefile").exists():
        run(["make", "build"])
    else:
        run(["uv", "run", "lektor", "build", "-O", "site"])


def ping_sitemaps(host: str) -> None:
    sitemap_url = f"{host}/sitemap.xml"
    print(f"Pinging search engines with {sitemap_url}")
    for name, template in PING_ENDPOINTS.items():
        url = template.format(sitemap=urllib.parse.quote(sitemap_url, safe=""))
        try:
            r = httpx.get(url, timeout=15, follow_redirects=True)
            print(f"  {name}: HTTP {r.status_code}")
        except Exception as exc:  # network errors are non-fatal here
            print(f"  {name}: ping failed ({exc})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish one video batch as a recrawl event.")
    parser.add_argument("--year", required=True, help="Edition year the batch belongs to.")
    parser.add_argument("--batch", required=True, help="Batch id under batches.<year> in recordings.yaml.")
    parser.add_argument("--no-build", action="store_true", help="Skip the site build step.")
    parser.add_argument("--no-ping", action="store_true", help="Skip the sitemap ping step.")
    parser.add_argument("--dry-run", action="store_true", help="No writes, no build, no ping.")
    args = parser.parse_args()

    cfg = load_recordings()
    batch = resolve_batch(cfg, args.year, args.batch)
    codes = [c.strip() for c in (batch.get("codes") or []) if str(c).strip()]
    title = batch.get("title") or args.batch
    print(f"Publishing batch '{args.batch}' ({title}) — {len(codes)} talk(s).")

    sync_batch(args.year, codes, args.dry_run)

    if args.dry_run:
        print("Dry run — skipping build and ping.")
        return

    if not args.no_build:
        build_site()

    if not args.no_ping:
        ping_sitemaps(canonical_host())

    print(
        "Batch published: sitemap <lastmod> moved, /llms-full-archive.txt regenerated, "
        "search engines pinged."
    )


if __name__ == "__main__":
    main()
