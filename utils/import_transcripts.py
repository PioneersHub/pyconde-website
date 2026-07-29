"""
Import speaker-diarized transcripts into talk contents.lr files.

Source layout (one folder per session, Pretalx code prefix):
    {SRC}/{CODE}-{Speaker Names}/transcript.md
    {SRC}/{CODE}-{Speaker Names}/transcript.json
    {SRC}/{CODE}-{Speaker Names}/transcript.{txt,speakers.txt}

Behaviour, per matching talk:
  - Strip the YAML front-matter (between '---' fences) at the top of transcript.md
  - Strip the redundant H1 title and the "**Speakers/Date/Room/...**" metadata bullets
  - Keep the body starting at the first speaker block (e.g. '**Speaker 1** _[mm:ss]_')
  - Replace or append a `transcript:` markdown field on the talk's contents.lr
  - Set transcript_status = auto, transcript_language = en

Talks whose Pretalx code has no matching folder are left untouched.
Folders whose code has no matching talk are reported as orphans.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import lektor_lr

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path.home() / "Documents" / "Claude" / "2025-transcripts"

# Pretalx codes are 6 chars, [A-Z0-9]. Source folders come in shapes like
# "{CODE}", "{CODE}-{Speaker Names}", "{CODE} 2" (de-dup suffix), etc.
CODE_RE = re.compile(r"^([A-Z0-9]{6})(?:[-_ .]|$)")

# YAML front-matter at the very top, between two '---' lines
FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)

# A line that opens a speaker block (works for "**Speaker 1**", "**Speaker 2** _[00:08]_", etc.)
SPEAKER_BLOCK_RE = re.compile(r"^\*\*Speaker\s+\d+\*\*", re.MULTILINE)


def extract_code(folder_name: str) -> str | None:
    m = CODE_RE.match(folder_name)
    return m.group(1) if m else None


def clean_transcript(raw: str) -> str:
    """Strip front-matter and the redundant H1/metadata block; keep speaker body."""
    body = FRONT_MATTER_RE.sub("", raw, count=1)
    m = SPEAKER_BLOCK_RE.search(body)
    if m:
        return body[m.start():].rstrip() + "\n"
    # No speaker blocks found — fall back to stripping the H1+metadata section
    # by dropping until the first "## Transcript" heading
    sp = body.find("## Transcript")
    if sp != -1:
        return body[sp:].rstrip() + "\n"
    return body.rstrip() + "\n"


def import_one(talk_dir: Path, transcript_md: Path, status: str, language: str, dry_run: bool) -> None:
    contents = talk_dir / "contents.lr"
    if not contents.exists():
        print(f"  skip: no contents.lr at {contents}", file=sys.stderr)
        return
    raw_md = transcript_md.read_text(encoding="utf-8")
    body = clean_transcript(raw_md)
    if not body.strip():
        print(f"  skip: empty body for {talk_dir.name}", file=sys.stderr)
        return

    text, fields = lektor_lr.read_lr(contents)
    if not lektor_lr.round_trip_ok(text, fields):
        raise SystemExit(f"Refusing to write: {contents} does not round-trip.")

    lektor_lr.upsert_fields(
        fields,
        {
            # Trailing newlines are stripped so the field ends exactly where
            # the `---` separator begins — the shape already on disk, which
            # keeps a re-import diff-free.
            "transcript": body.rstrip("\n"),
            "transcript_status": status,
            "transcript_language": language,
        },
    )

    new_text = lektor_lr.serialize_lr(fields)
    if dry_run:
        print(f"  would update {contents} (+transcript {len(body)} chars)")
        return
    contents.write_text(new_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="Source root with {CODE}-... folders")
    parser.add_argument("--year", default="2025", help="Edition year (looks under content/archive/{year}/talks/)")
    parser.add_argument("--status", default="auto", choices=["none", "auto", "reviewed", "official"])
    parser.add_argument("--language", default="en")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    year = lektor_lr.current_year() if args.year == "current" else args.year
    talks_root = lektor_lr.talks_dir_for_year(year)
    if not talks_root.is_dir():
        print(f"talks root not found: {talks_root}", file=sys.stderr)
        return 2
    if not args.src.is_dir():
        print(f"source not found: {args.src}", file=sys.stderr)
        return 2

    # CODE -> talk-folder lookup. After the slug migration the folder name is
    # the slug, so a name-based lookup would land on the redirect stub rather
    # than the talk. See utils/lektor_lr.py.
    code_to_folder = lektor_lr.build_code_index(talks_root)

    imported = 0
    skipped_no_md = 0
    skipped_dup: list[str] = []
    orphans: list[str] = []
    seen_codes: set[str] = set()

    for entry in sorted(args.src.iterdir()):
        if not entry.is_dir():
            continue
        code = extract_code(entry.name)
        if not code:
            continue
        if code in seen_codes:
            # Two source folders share the same code (e.g. "ABC123" and
            # "ABC123 2"). Take the first only; flag the rest so the
            # operator can investigate.
            skipped_dup.append(entry.name)
            continue
        seen_codes.add(code)
        target_folder = code_to_folder.get(code)
        if target_folder is None:
            orphans.append(entry.name)
            continue
        transcript_md = entry / "transcript.md"
        if not transcript_md.exists():
            skipped_no_md += 1
            print(f"  skip: no transcript.md in {entry.name}", file=sys.stderr)
            continue
        print(f"  import: {code} ({target_folder.name}) ← {entry.name}")
        import_one(target_folder, transcript_md, args.status, args.language, args.dry_run)
        imported += 1

    print()
    print(f"imported:   {imported}")
    print(f"no-md:      {skipped_no_md}")
    print(f"duplicate:  {len(skipped_dup)}")
    for d in skipped_dup:
        print(f"  - {d}")
    print(f"orphans:    {len(orphans)}")
    for o in orphans:
        print(f"  - {o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
