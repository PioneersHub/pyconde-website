"""Import Pretalx submission resources into talk pages.

Speakers attach their slide decks and repos to the submission itself far
more often than they answer the two free-text resource questions: for the
2026 edition 98 of 145 submissions carry `resources`, against 47 with a
`supporting_material_url` answer and 15 with a `slides_link`. Those
attachments never reached the site, so most talk pages showed no material
at all even though the speaker had uploaded some.

Source layout — one raw submission dump per talk, keyed by Pretalx code:

    {SRC}/{CODE}.json  ->  {"code": "...", "resources": [{"resource": url,
                                                          "description": str}]}

The rendering is `talks.resources_to_lines`, the same function the live
Pretalx importer uses, so a backfilled page and a freshly imported one are
byte-identical.

Previews are a separate, later step: utils/generate_resource_thumbs.py
appends a third segment to the lines it can render. This importer never
discards one — a re-import keeps the preview attached to its resource.

Talks are resolved through `lektor_lr.build_code_index()`, i.e. by each
talk's `code:` field — never by folder name, which after the slug migration
belongs to a `_model: redirect` stub. Re-running is idempotent: unchanged
markdown writes nothing, and only the `resources` field is ever touched.

    uv run python utils/import_resources.py --src ~/dumps/2026 --year 2026 --dry-run
    uv run python utils/import_resources.py --src ~/dumps/2026 --year 2026
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import lektor_lr
from talks import RESOURCE_SEP, parse_resource_line, resources_to_lines

REPO = Path(__file__).resolve().parent.parent

TALK_FIELD = "resources"


def read_resources(path: Path) -> str:
    """Return one submission's resources as `label | url` lines, '' when none."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  skip: cannot read {path.name}: {exc}", file=sys.stderr)
        return ""
    if not isinstance(data, dict):
        print(f"  skip: {path.name} is not a JSON object", file=sys.stderr)
        return ""
    return resources_to_lines(data.get("resources"))


def keep_previews(fresh: str, existing: str) -> str:
    """Carry generated preview paths across a re-import, matched by URL.

    Previews are produced separately and appended as a third segment. A
    re-import rebuilds the lines from Pretalx, which knows nothing about
    them, so without this the generator would have to run again after
    every import.
    """
    previews = {}
    for line in existing.splitlines():
        _, url, preview = parse_resource_line(line)
        if url and preview:
            previews[url] = preview

    merged = []
    for line in fresh.splitlines():
        _, url, _ = parse_resource_line(line)
        preview = previews.get(url)
        merged.append(f"{line}{RESOURCE_SEP}{preview}" if preview else line)
    return "\n".join(merged)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, required=True, help="Directory of {CODE}.json submission dumps")
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

        fresh = read_resources(record)
        if not fresh:
            counts["empty"] += 1
            continue

        lr_path = talk_dir / "contents.lr"
        text, fields = lektor_lr.read_lr(lr_path)
        # Never write a redirect stub, never write a file the parser cannot
        # reproduce — the same two guards the other importers use.
        if lektor_lr.is_redirect(fields):
            raise SystemExit(f"Refusing to write: {lr_path} is a redirect stub.")
        if not lektor_lr.round_trip_ok(text, fields):
            raise SystemExit(f"Refusing to write: {lr_path} does not round-trip.")

        merged = keep_previews(fresh, lektor_lr.field_value(fields, TALK_FIELD, "") or "")
        if lektor_lr.field_value(fields, TALK_FIELD, "") == merged:
            counts["unchanged"] += 1
            continue

        rel = lr_path.relative_to(REPO)
        n = merged.count("\n") + 1
        if args.dry_run:
            counts["imported"] += 1
            print(f"  {code}: would-import  {n} resource(s)  -> {rel}")
            continue

        lektor_lr.upsert_fields(fields, {TALK_FIELD: merged})
        lektor_lr.write_lr(lr_path, fields)
        counts["imported"] += 1
        print(f"  {code}: imported  {n} resource(s)  -> {rel}")

    if orphans:
        print(f"\n  {len(orphans)} dump(s) with no matching talk: {', '.join(orphans)}")

    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
