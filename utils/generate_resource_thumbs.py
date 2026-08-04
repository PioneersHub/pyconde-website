"""Render preview images for the files attached to talk submissions.

Pretalx serves its uploads with `Content-Disposition: attachment`, so a
browser downloads a deck rather than showing it — the talk page cannot
preview one by pointing at the URL. This script downloads each attachment
once, renders its first page to a small PNG, and writes the path back into
the talk's `resources` field as a third segment:

    Slides | https://pretalx.com/…/deck.pdf | /static/media/resources/ABC123-1.png

Rendering is macOS Quick Look (`qlmanage -t`), which handles PDF, PPTX,
KEY and the rest of the deck formats speakers upload without pulling in a
PDF stack. **That makes this a local, macOS-only utility** — like the
transcript importer, it is run by hand and its output is committed, so CI
and Linux contributors are unaffected.

External links (GitHub, Canva, SpeakerDeck…) are skipped: previewing them
would need a headless browser, and the talk page renders them as typed
cards instead.

Re-running is cheap and idempotent: a resource whose PNG already exists is
skipped, and only the `resources` field is ever rewritten.

    uv run python utils/generate_resource_thumbs.py --year 2026 --dry-run
    uv run python utils/generate_resource_thumbs.py --year 2026
    uv run python utils/generate_resource_thumbs.py --year 2026 --force
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

import lektor_lr
from PIL import Image
from talks import RESOURCE_SEP, parse_resource_line

REPO = Path(__file__).resolve().parent.parent
THUMB_DIR = REPO / "assets" / "static" / "media" / "resources"
THUMB_URL_PREFIX = "/static/media/resources"

TALK_FIELD = "resources"

# Formats Quick Look renders reliably. Anything else (archives, source
# files, bare links) gets no preview and falls back to a typed card.
PREVIEWABLE = {".pdf", ".pptx", ".ppt", ".key", ".odp", ".docx", ".pages"}

# Retina-friendly: the card shows the strip at half these pixels.
THUMB_HEIGHT = 224
QUICKLOOK_SIZE = 600
DOWNLOAD_TIMEOUT = 60
# Decks run large (the biggest 2026 upload is 9 MB); anything past this is
# a sign the URL is not what we think it is.
MAX_DOWNLOAD_BYTES = 80 * 1024 * 1024

USER_AGENT = "pyconde-website resource-thumbnailer (+https://pycon.de)"


def previewable(url: str) -> bool:
    """True when the URL points at a file Quick Look can render."""
    return Path(unquote(urlparse(url).path)).suffix.lower() in PREVIEWABLE


def download(url: str, dest: Path) -> bool:
    """Fetch one attachment. Returns False (with a reason) on any failure."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response:
            length = int(response.headers.get("Content-Length") or 0)
            if length > MAX_DOWNLOAD_BYTES:
                print(f"    skip: {length} bytes exceeds the size limit", file=sys.stderr)
                return False
            payload = response.read(MAX_DOWNLOAD_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"    skip: download failed ({exc})", file=sys.stderr)
        return False
    if len(payload) > MAX_DOWNLOAD_BYTES:
        print("    skip: body exceeds the size limit", file=sys.stderr)
        return False
    dest.write_bytes(payload)
    return True


def render_thumbnail(source: Path, out_png: Path) -> bool:
    """Render page one of `source` into `out_png`, scaled to THUMB_HEIGHT."""
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            ["qlmanage", "-t", "-s", str(QUICKLOOK_SIZE), "-o", tmp, str(source)],
            capture_output=True,
            text=True,
            check=False,
        )
        rendered = sorted(Path(tmp).glob("*.png"))
        if not rendered:
            detail = (result.stderr or result.stdout or "").strip().splitlines()
            print(f"    skip: Quick Look produced nothing ({detail[-1] if detail else 'no output'})", file=sys.stderr)
            return False
        with Image.open(rendered[0]) as opened:
            page = opened.convert("RGB")
        width = max(1, round(page.width * THUMB_HEIGHT / page.height))
        page = page.resize((width, THUMB_HEIGHT), Image.LANCZOS)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        page.save(out_png, "PNG", optimize=True)
    return True


def preview_talk(code: str, existing: str, counts: dict, *, force: bool, dry_run: bool) -> str:
    """Return one talk's `resources` field with every renderable line previewed."""
    lines = []
    for index, line in enumerate(existing.splitlines(), start=1):
        label, url, _ = parse_resource_line(line)
        plain = f"{label}{RESOURCE_SEP}{url}"
        if not url:
            lines.append(line)
            continue
        if not previewable(url):
            counts["not-previewable"] += 1
            lines.append(plain)
            continue

        png = THUMB_DIR / f"{code}-{index}.png"
        with_preview = f"{plain}{RESOURCE_SEP}{THUMB_URL_PREFIX}/{png.name}"
        if png.exists() and not force:
            counts["kept"] += 1
            lines.append(with_preview)
            continue
        if dry_run:
            counts["rendered"] += 1
            print(f"  {code}: would render {png.name} <- {url}")
            lines.append(with_preview)
            continue

        with tempfile.TemporaryDirectory() as tmp:
            suffix = Path(unquote(urlparse(url).path)).suffix.lower()
            downloaded = Path(tmp) / f"{code}-{index}{suffix}"
            print(f"  {code}: rendering {png.name} <- {url}")
            ok = download(url, downloaded) and render_thumbnail(downloaded, png)
        if ok:
            counts["rendered"] += 1
            lines.append(with_preview)
        else:
            # Keep the resource, drop only its preview segment, so the page
            # falls back to a typed card.
            counts["failed"] += 1
            lines.append(plain)

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", default="2026", help="Edition year, or 'current'")
    parser.add_argument("--force", action="store_true", help="Re-render previews that already exist")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not shutil.which("qlmanage"):
        print("qlmanage not found — this utility needs macOS Quick Look.", file=sys.stderr)
        return 2

    year = lektor_lr.current_year() if args.year == "current" else args.year
    talks_root = lektor_lr.talks_dir_for_year(year)
    if not talks_root.is_dir():
        print(f"talks root not found: {talks_root}", file=sys.stderr)
        return 2

    code_index = lektor_lr.build_code_index(talks_root)
    print(f"Indexed {len(code_index)} talks by Pretalx code under {talks_root}.")

    counts = {"rendered": 0, "kept": 0, "not-previewable": 0, "failed": 0, "talks-updated": 0}

    for code, talk_dir in sorted(code_index.items()):
        lr_path = talk_dir / "contents.lr"
        text, fields = lektor_lr.read_lr(lr_path)
        existing = lektor_lr.field_value(fields, TALK_FIELD, "") or ""
        if not existing.strip():
            continue
        if lektor_lr.is_redirect(fields):
            raise SystemExit(f"Refusing to write: {lr_path} is a redirect stub.")
        if not lektor_lr.round_trip_ok(text, fields):
            raise SystemExit(f"Refusing to write: {lr_path} does not round-trip.")

        merged = preview_talk(code, existing, counts, force=args.force, dry_run=args.dry_run)
        if merged == existing or args.dry_run:
            continue
        lektor_lr.upsert_fields(fields, {TALK_FIELD: merged})
        lektor_lr.write_lr(lr_path, fields)
        counts["talks-updated"] += 1

    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
