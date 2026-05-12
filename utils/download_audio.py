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

Requires `yt-dlp` on PATH (e.g. `brew install yt-dlp`). The script shells
out to the binary rather than importing it as a Python module, so the
system install is always used and stays up-to-date independently of the
project's Python dependencies.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

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


def download_one(job: Job, dest_dir: Path, format_id: str, ytdlp: str, dry_run: bool) -> tuple[str, str]:
    """Run yt-dlp for a single job. Returns (status, detail)."""
    out_path = dest_dir / f"{job.stem}.m4a"
    if out_path.exists() and out_path.stat().st_size > 0:
        return ("skip-exists", out_path.name)
    if dry_run:
        return ("would-download", f"{job.youtube_id} → {out_path.name}")

    url = f"https://www.youtube.com/watch?v={job.youtube_id}"
    # Output template uses %(ext)s so yt-dlp picks the actual file extension
    # served (almost always m4a for bestaudio[ext=m4a]).
    out_tmpl = str(dest_dir / f"{job.stem}.%(ext)s")
    cmd = [
        ytdlp,
        "-f", format_id,
        "-o", out_tmpl,
        "--no-progress",
        "--no-warnings",
        "--retries", "3",
        "--fragment-retries", "3",
        url,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ("fail", f"yt-dlp not found at {ytdlp}")

    if result.returncode != 0:
        # Last non-empty line of stderr is usually the actionable bit
        tail = next(
            (line for line in reversed(result.stderr.splitlines()) if line.strip()),
            "yt-dlp exited non-zero with no output",
        )
        return ("fail", tail)

    if out_path.exists():
        return ("ok", out_path.name)
    # Format selector picked a non-m4a stream; find what it actually wrote.
    candidates = list(dest_dir.glob(f"{job.stem}.*"))
    if candidates:
        return ("ok-other", candidates[0].name)
    return ("fail", "output file not produced")


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
    p.add_argument(
        "--ytdlp",
        default=None,
        help="Path to the yt-dlp binary. Default: first match on PATH.",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    ytdlp = args.ytdlp or shutil.which("yt-dlp")
    if not ytdlp and not args.dry_run:
        print(
            "yt-dlp not found on PATH. Install with `brew install yt-dlp` "
            "(macOS) or your platform's equivalent, then re-run.",
            file=sys.stderr,
        )
        return 2
    if shutil.which("ffmpeg") is None and not args.dry_run:
        print(
            "Note: ffmpeg is not on PATH. The default format selector still works "
            "for m4a-native streams; if you hit 'requires ffmpeg' errors, install "
            "ffmpeg or pass --format 'bestaudio[ext=m4a]'.",
            file=sys.stderr,
        )

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
            status, detail = download_one(job, dest_root, args.format, ytdlp or "yt-dlp", args.dry_run)
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
    sys.exit(main())
