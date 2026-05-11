"""
Generate per-edition track index + per-track pages from talk content.

For each edition (current /talks/ + every /archive/{year}/talks/), scan all
talks, collect the unique `track` values, slugify them, and write:

  content/tracks/                       (current edition)
    contents.lr                         (_model: tracks)
    {slug}/contents.lr                  (_model: track)

  content/archive/{year}/tracks/
    contents.lr                         (_model: tracks)
    {slug}/contents.lr                  (_model: track)

Idempotent: re-runs replace generated content, leaving talk content alone.
Track pages declare just (name, slug, year, talk_count); the template
re-queries siblings at render time to list the actual talks (so we don't
have to embed talk codes here).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTENT = REPO / "content"


def slugify(s: str) -> str:
    s = s.lower()
    # Drop accents
    import unicodedata

    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "untitled"


def extract_track(lr_text: str) -> str | None:
    for line in lr_text.split("\n"):
        if line.startswith("track:"):
            t = line.split(":", 1)[1].strip()
            if t and t.lower() != "none":
                return t
            return None
    return None


def collect_tracks(talks_dir: Path) -> dict[str, list[str]]:
    """Return {track_label: [pretalx_code, ...]} for the given talks dir."""
    out: dict[str, list[str]] = {}
    if not talks_dir.is_dir():
        return out
    for talk in sorted(talks_dir.iterdir()):
        lr = talk / "contents.lr"
        if not lr.exists():
            continue
        track = extract_track(lr.read_text(encoding="utf-8"))
        if track is None:
            continue
        out.setdefault(track, []).append(talk.name)
    return out


def write_tracks_index(tracks_dir: Path, year: str, title: str) -> None:
    tracks_dir.mkdir(parents=True, exist_ok=True)
    body = f"""_model: tracks
---
title: {title}
---
year: {year}
"""
    (tracks_dir / "contents.lr").write_text(body, encoding="utf-8")


def write_track_page(track_dir: Path, name: str, slug: str, year: str, count: int) -> None:
    track_dir.mkdir(parents=True, exist_ok=True)
    body = f"""_model: track
---
name: {name}
---
slug: {slug}
---
year: {year}
---
talk_count: {count}
"""
    (track_dir / "contents.lr").write_text(body, encoding="utf-8")


def clear_existing(tracks_dir: Path) -> None:
    """Delete sub-directories under tracks_dir (but not tracks_dir itself)."""
    if not tracks_dir.is_dir():
        return
    for child in tracks_dir.iterdir():
        if child.is_dir():
            for f in child.rglob("*"):
                if f.is_file():
                    f.unlink()
            child.rmdir()


def process(talks_dir: Path, tracks_dir: Path, year_label: str, title: str, dry_run: bool) -> int:
    by_track = collect_tracks(talks_dir)
    if not by_track:
        return 0
    if dry_run:
        print(f"  would write index + {len(by_track)} tracks at {tracks_dir}")
        for label, codes in sorted(by_track.items()):
            print(f"    {slugify(label):<50} ({len(codes)} talks)  {label}")
        return len(by_track)
    clear_existing(tracks_dir)
    write_tracks_index(tracks_dir, year=year_label, title=title)
    for label, codes in by_track.items():
        slug = slugify(label)
        write_track_page(tracks_dir / slug, label, slug, year_label, len(codes))
    print(f"  wrote {len(by_track)} tracks at {tracks_dir}")
    return len(by_track)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    total = 0
    # Current edition
    cur_talks = CONTENT / "talks"
    if cur_talks.is_dir():
        total += process(cur_talks, CONTENT / "tracks", year_label="",
                         title="Tracks", dry_run=args.dry_run)

    # Archive editions
    for year_dir in sorted((CONTENT / "archive").iterdir()):
        if not year_dir.is_dir():
            continue
        year = year_dir.name
        if not year.isdigit():
            continue
        talks = year_dir / "talks"
        out = year_dir / "tracks"
        title = f"Tracks at PyCon DE & PyData {year}"
        total += process(talks, out, year_label=year, title=title, dry_run=args.dry_run)

    print()
    print(f"tracks generated total: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
