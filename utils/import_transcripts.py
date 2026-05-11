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

REPO = Path(__file__).resolve().parent.parent
TALKS_ROOT = REPO / "content" / "archive" / "2025" / "talks"
DEFAULT_SRC = Path.home() / "Documents" / "Claude" / "2025-transcripts"

# Pretalx codes are 6 chars, [A-Z0-9]
CODE_RE = re.compile(r"^([A-Z0-9]{6})(?:-|$)")

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


def parse_lr(text: str) -> list[tuple[str, str]]:
    """Lektor .lr parser: returns list of (field_name, value) preserving order.

    Lektor convention: a multi-line field is written as "name:\\n\\n<body>";
    we strip the single leading blank line so the serializer can add it back
    without doubling.
    """
    fields: list[tuple[str, str]] = []
    current_name: str | None = None
    current_buf: list[str] = []
    inline_value_present = False
    for line in text.split("\n"):
        if line == "---":
            if current_name is not None:
                value = "\n".join(current_buf).rstrip("\n")
                # If the field is multi-line (no inline value), strip one
                # leading blank line that is part of the Lektor separator.
                if not inline_value_present and value.startswith("\n"):
                    value = value[1:]
                fields.append((current_name, value))
            current_name = None
            current_buf = []
            inline_value_present = False
            continue
        if current_name is None:
            m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s?(.*)$", line)
            if not m:
                continue
            current_name = m.group(1)
            rest = m.group(2)
            if rest:
                inline_value_present = True
                current_buf = [rest]
            else:
                inline_value_present = False
                current_buf = []
        else:
            current_buf.append(line)
    if current_name is not None:
        value = "\n".join(current_buf).rstrip("\n")
        if not inline_value_present and value.startswith("\n"):
            value = value[1:]
        fields.append((current_name, value))
    return fields


def serialize_lr(fields: list[tuple[str, str]]) -> str:
    out: list[str] = []
    for i, (name, value) in enumerate(fields):
        if i > 0:
            out.append("---")
        if "\n" in value:
            out.append(f"{name}:")
            out.append("")
            out.append(value)
        else:
            out.append(f"{name}: {value}" if value else f"{name}:")
    return "\n".join(out) + "\n"


def upsert_field(fields: list[tuple[str, str]], name: str, value: str) -> list[tuple[str, str]]:
    for i, (n, _) in enumerate(fields):
        if n == name:
            fields[i] = (name, value)
            return fields
    fields.append((name, value))
    return fields


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

    fields = parse_lr(contents.read_text(encoding="utf-8"))
    fields = upsert_field(fields, "transcript", body)
    fields = upsert_field(fields, "transcript_status", status)
    fields = upsert_field(fields, "transcript_language", language)

    new_text = serialize_lr(fields)
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

    if args.year == "current":
        talks_root = REPO / "content" / "talks"
    else:
        talks_root = REPO / "content" / "archive" / args.year / "talks"
    if not talks_root.is_dir():
        print(f"talks root not found: {talks_root}", file=sys.stderr)
        return 2
    if not args.src.is_dir():
        print(f"source not found: {args.src}", file=sys.stderr)
        return 2

    existing_codes = {p.name for p in talks_root.iterdir() if p.is_dir()}
    imported = 0
    skipped_no_md = 0
    orphans: list[str] = []

    for entry in sorted(args.src.iterdir()):
        if not entry.is_dir():
            continue
        code = extract_code(entry.name)
        if not code:
            continue
        if code not in existing_codes:
            orphans.append(entry.name)
            continue
        transcript_md = entry / "transcript.md"
        if not transcript_md.exists():
            skipped_no_md += 1
            print(f"  skip: no transcript.md in {entry.name}", file=sys.stderr)
            continue
        print(f"  import: {code} ← {entry.name}")
        import_one(talks_root / code, transcript_md, args.status, args.language, args.dry_run)
        imported += 1

    print()
    print(f"imported:   {imported}")
    print(f"no-md:      {skipped_no_md}")
    print(f"orphans:    {len(orphans)}")
    for o in orphans:
        print(f"  - {o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
