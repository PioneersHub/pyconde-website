"""Import per-session recaps from the py_tube records into talk pages.

The py_tube pipeline produces one JSON record per session, keyed by Pretalx
code, describing what the talk *actually covered* — derived from the recording.
That is a different thing from `abstract` / `full_description`, which are the
speaker's proposal written months before the conference. This importer copies
`sm_long_text` into each talk's `recap` field, which templates/talk.html renders
as the page body while the original submission text moves into a collapsible.

Source layout:

    {SRC}/{CODE}.json  ->  {"pretalx_id": "...", "sm_long_text": "...", ...}

Talks are resolved through `lektor_lr.build_code_index()`, i.e. by each talk's
`code:` field — never by folder name. After the slug migration the code-named
folder is a `_model: redirect` stub, and writing to it would destroy a redirect
and publish a duplicate talk page. See utils/lektor_lr.py.

Re-running is idempotent: unchanged text writes nothing, and only the `recap`
field is ever rewritten — every other byte of contents.lr is preserved.

    uv run python utils/import_session_records.py --year 2026 --dry-run
    uv run python utils/import_session_records.py --year 2026
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import lektor_lr

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path.home() / "code/pioneershub/py_tube/projects/pyconde-pydata-2026/records"

# The attribute carrying the long-form recap in each record.
RECORD_FIELD = "sm_long_text"
TALK_FIELD = "recap"


def read_recap(path: Path) -> str:
    """Return the recap text from one record, or '' when absent/blank."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  skip: cannot read {path.name}: {exc}", file=sys.stderr)
        return ""
    if not isinstance(data, dict):
        print(f"  skip: {path.name} is not a JSON object", file=sys.stderr)
        return ""
    return (data.get(RECORD_FIELD) or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="Directory of {CODE}.json records")
    parser.add_argument("--year", default="2026", help="Edition year, or 'current'")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.src.is_dir():
        print(f"source not found: {args.src}", file=sys.stderr)
        return 2

    year = lektor_lr.current_year() if args.year == "current" else args.year
    talks_root = lektor_lr.talks_dir_for_year(year)
    if not talks_root.is_dir():
        print(f"talks root not found: {talks_root}", file=sys.stderr)
        return 2

    code_index = lektor_lr.build_code_index(talks_root)
    print(f"Indexed {len(code_index)} talks by Pretalx code under {talks_root}.")

    counts = {"imported": 0, "unchanged": 0, "empty": 0, "orphan": 0}
    orphans: list[str] = []

    for record in sorted(args.src.glob("*.json")):
        code = record.stem
        talk_dir = code_index.get(code)
        if talk_dir is None:
            counts["orphan"] += 1
            orphans.append(code)
            continue

        recap = read_recap(record)
        if not recap:
            counts["empty"] += 1
            print(f"  {code}: empty {RECORD_FIELD}, skipped")
            continue

        lr_path = talk_dir / "contents.lr"
        text, fields = lektor_lr.read_lr(lr_path)
        # Same two guards the recording sync uses: never write a redirect stub,
        # never write a file the parser cannot reproduce.
        if lektor_lr.is_redirect(fields):
            raise SystemExit(f"Refusing to write: {lr_path} is a redirect stub.")
        if not lektor_lr.round_trip_ok(text, fields):
            raise SystemExit(f"Refusing to write: {lr_path} does not round-trip.")

        if lektor_lr.field_value(fields, TALK_FIELD, "") == recap:
            counts["unchanged"] += 1
            continue

        rel = lr_path.relative_to(REPO)
        if args.dry_run:
            counts["imported"] += 1
            print(f"  {code}: would-import  {len(recap):>5} chars  -> {rel}")
            continue

        lektor_lr.upsert_fields(fields, {TALK_FIELD: recap})
        lektor_lr.write_lr(lr_path, fields)
        counts["imported"] += 1
        print(f"  {code}: imported  {len(recap):>5} chars  -> {rel}")

    if orphans:
        print(f"\n  {len(orphans)} record(s) with no matching talk: {', '.join(orphans)}")

    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
