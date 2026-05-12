"""
Download m4a audio for every talk that has a linked YouTube recording, so the
audio can be fed into the transcription pipeline later.

Per edition:
  ~/Documents/Claude/{year}-audio/
    {CODE}-{slug-or-title}.m4a
    _download_log.txt

Talks without a `youtube_id`, with `do_not_record: yes`, or whose audio file
already exists are skipped. Re-running the script is therefore resumable —
only new or previously-failed downloads are attempted.

Requires `yt-dlp` (declared as a dev dependency in pyproject.toml).
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

REPO = Path(__file__).resolve().parent.parent


def slugify(s: str, max_len: int = 80) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:max_len].rstrip("-")


def field(lr_text: str, name: str) -> str | None:
    """Return the value of a single-line .lr field, or None."""
    for line in lr_text.split("\n"):
        if line.startswith(f"{name}:"):
            rest = line.split(":", 1)[1].strip()
            return rest or None
    return None


@dataclass
class Job:
    code: str
    slug: str
    title: str
    youtube_id: str
    talk_folder: Path

    @property
    def stem(self) -> str:
        # Prefer the existing slug (frozen at migration time); fall back to a
        # fresh slugify of the title.
        slug = self.slug or slugify(self.title) or "untitled"
        return f"{self.code}-{slug}"


def collect_jobs(talks_dir: Path) -> list[Job]:
    """Return one Job per talk that has a youtube_id and isn't do_not_record."""
    jobs: list[Job] = []
    for d in sorted(talks_dir.iterdir()):
        if not d.is_dir():
            continue
        lr = d / "contents.lr"
        if not lr.exists():
            continue
        text = lr.read_text(encoding="utf-8", errors="ignore")
        if "_model: redirect" in text:
            continue
        ytid = field(text, "youtube_id")
        if not ytid:
            continue
        if (field(text, "do_not_record") or "").lower() == "yes":
            continue
        code = field(text, "code") or d.name
        slug = field(text, "slug") or d.name
        title = field(text, "title") or ""
        jobs.append(Job(code=code, slug=slug, title=title, youtube_id=ytid, talk_folder=d))
    return jobs


def download_one(job: Job, dest_dir: Path, format_id: str, dry_run: bool) -> tuple[str, str]:
    """Run yt-dlp for a single job. Returns (status, detail)."""
    out_path = dest_dir / f"{job.stem}.m4a"
    if out_path.exists() and out_path.stat().st_size > 0:
        return ("skip-exists", str(out_path.name))
    if dry_run:
        return ("would-download", f"{job.youtube_id} → {out_path.name}")

    # yt-dlp options. We ask for the best m4a-compatible audio-only stream
    # and disable post-processing extraction (no ffmpeg dependency) — m4a
    # is shipped as-is by YouTube for most videos.
    opts = {
        "format": format_id,
        "outtmpl": str(dest_dir / f"{job.stem}.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "ignoreerrors": False,
        # Replace illegal filename chars rather than refusing to download
        "restrictfilenames": False,
        # Don't write metadata sidecar files
        "writeinfojson": False,
        "writethumbnail": False,
        # Cap retries on a bad stream — fail fast and report
        "retries": 3,
        "fragment_retries": 3,
    }
    url = f"https://www.youtube.com/watch?v={job.youtube_id}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        return ("fail", str(e).splitlines()[-1] if str(e) else "download error")
    except Exception as e:  # noqa: BLE001
        return ("fail", f"{type(e).__name__}: {e}")

    # yt-dlp may pick an alternate extension if m4a isn't available; verify.
    if not out_path.exists():
        # Look for sibling with same stem but different extension
        candidates = list(dest_dir.glob(f"{job.stem}.*"))
        if candidates:
            return ("ok-other", candidates[0].name)
        return ("fail", "output file not produced")
    return ("ok", out_path.name)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--year",
        required=True,
        help="Edition year ('2018'…'2025') or 'current' for the in-flight edition, "
        "or 'all' to walk every archived edition.",
    )
    p.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Output root. Default: ~/Documents/Claude/{year}-audio",
    )
    p.add_argument(
        "--format",
        default="bestaudio[ext=m4a]/bestaudio",
        help="yt-dlp format selector (default: bestaudio[ext=m4a]/bestaudio)",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.year == "all":
        years = sorted(
            d.name for d in (REPO / "content" / "archive").iterdir()
            if d.is_dir() and d.name.isdigit()
        )
    else:
        years = [args.year]

    grand_total = 0
    grand_ok = 0
    grand_skip = 0
    grand_fail: list[tuple[str, str, str]] = []

    for year in years:
        if year == "current":
            talks_dir = REPO / "content" / "talks"
            dest_root = args.dest or Path.home() / "Documents" / "Claude" / "current-audio"
        else:
            talks_dir = REPO / "content" / "archive" / year / "talks"
            dest_root = args.dest or Path.home() / "Documents" / "Claude" / f"{year}-audio"

        if not talks_dir.is_dir():
            print(f"skip {year}: {talks_dir} not found", file=sys.stderr)
            continue

        jobs = collect_jobs(talks_dir)
        if not jobs:
            print(f"-- {year}: no talks with a youtube_id, skipping")
            continue

        dest_root.mkdir(parents=True, exist_ok=True)
        log = dest_root / "_download_log.txt"
        log_fh = log.open("a", encoding="utf-8") if not args.dry_run else None
        if log_fh:
            log_fh.write(f"\n=== run for {year} ===\n")

        print(f"-- {year}: {len(jobs)} talks with audio → {dest_root}")
        ok = skip = fail = 0
        for i, job in enumerate(jobs, 1):
            status, detail = download_one(job, dest_root, args.format, args.dry_run)
            line = f"  [{i:3}/{len(jobs)}] {status:<14} {job.code}  {detail}"
            print(line)
            if log_fh:
                log_fh.write(line + "\n")
            if status in {"ok", "ok-other", "would-download"}:
                ok += 1
            elif status == "skip-exists":
                skip += 1
            else:
                fail += 1
                grand_fail.append((year, job.code, detail))
        if log_fh:
            log_fh.close()
        print(f"   {year}: ok={ok}  skip-exists={skip}  fail={fail}")
        grand_total += len(jobs)
        grand_ok += ok
        grand_skip += skip

    print()
    print(f"TOTAL: {grand_ok} downloaded/would, {grand_skip} already present, "
          f"{len(grand_fail)} failed out of {grand_total} candidates.")
    if grand_fail:
        print("Failures:")
        for year, code, detail in grand_fail:
            print(f"  {year} {code}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    if shutil.which("ffmpeg") is None:
        print(
            "Note: ffmpeg is not on PATH. The default format selector still works for "
            "m4a-native streams; if you hit 'requires ffmpeg' errors, install ffmpeg or "
            "pass --format 'bestaudio[ext=m4a]'.",
            file=sys.stderr,
        )
    sys.exit(main())
