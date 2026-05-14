"""
Build a structured YAML inventory of every speaker image on the site.

Walks every speaker record under content/speakers/ and
content/archive/{year}/speakers/, groups by Pretalx code (so a speaker
who appears in multiple editions with the same code becomes one entry
spanning those editions), and writes the result as databags/speaker_images.yaml.

Schema (open — future runs may add fields without breaking existing ones):

  entries:
    - type: person                    # entity type
      role: speaker                   # role in this dataset
      pretalx_id: 37RKBL              # primary key
      name: Darya Petrashka           # latest known name
      editions: [2024, 2025]          # all editions where this code appears
      images:                         # one or more — list, not a scalar
        - path: /static/media/…       # site-relative path
          kind: avatar                # avatar | banner | social_card | …
          source: pretalx             # provenance hint
          editions: [2024, 2025]      # which editions reference this image

Use case: a one-off seed. Re-runs are safe — the script reads the
existing YAML, preserves any hand-added fields (e.g. extra image
entries authors may insert later), and only refreshes the structural
fields it owns (name, editions, default avatar reference). Fields
the script doesn't recognise are passed through verbatim.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import OrderedDict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CONTENT = REPO / "content"
OUT = REPO / "databags" / "speaker_images.yaml"


def field(text: str, name: str) -> str | None:
    for line in text.split("\n"):
        if line.startswith(f"{name}:"):
            rest = line.split(":", 1)[1].strip()
            return rest or None
    return None


def is_redirect(text: str) -> bool:
    return "_model: redirect" in text


def walk_speakers() -> dict[str, dict]:
    """Return {code: {"name": ..., "editions": [...], "avatar": ...}}."""
    by_code: dict[str, dict] = OrderedDict()

    sources: list[tuple[Path, str]] = []
    cur = CONTENT / "speakers"
    if cur.is_dir():
        sources.append((cur, "current"))
    archive = CONTENT / "archive"
    if archive.is_dir():
        for year_dir in sorted(d for d in archive.iterdir() if d.is_dir() and d.name.isdigit()):
            sp = year_dir / "speakers"
            if sp.is_dir():
                sources.append((sp, year_dir.name))

    for speakers_dir, edition in sources:
        for d in sorted(speakers_dir.iterdir()):
            if not d.is_dir():
                continue
            lr = d / "contents.lr"
            if not lr.exists():
                continue
            text = lr.read_text(encoding="utf-8", errors="ignore")
            if is_redirect(text):
                continue
            code = field(text, "code") or d.name
            name = field(text, "name") or ""
            avatar = field(text, "avatar") or ""
            entry = by_code.setdefault(code, {
                "name": name,
                "editions": [],
                "avatar_by_edition": OrderedDict(),
            })
            # Keep the most recent edition's name (sources are walked
            # current → 2018, 2019, …, 2025 so "current" is first; we
            # want the latest non-empty name)
            if name:
                entry["name"] = name
            if edition not in entry["editions"]:
                entry["editions"].append(edition)
            if avatar:
                entry["avatar_by_edition"][edition] = avatar
    return by_code


def to_entries(by_code: dict[str, dict]) -> list[dict]:
    out: list[dict] = []
    for code, info in by_code.items():
        # Group identical avatar paths so the same image isn't duplicated
        # for every edition that references it.
        groups: dict[str, list[str]] = OrderedDict()
        for ed, avatar in info["avatar_by_edition"].items():
            groups.setdefault(avatar, []).append(ed)
        images = [
            {
                "path": path,
                "kind": "avatar",
                "source": "pretalx",
                "editions": eds,
            }
            for path, eds in groups.items()
        ]
        out.append({
            "type": "person",
            "role": "speaker",
            "pretalx_id": code,
            "name": info["name"],
            "editions": info["editions"],
            "images": images,
        })
    # Stable alpha sort by pretalx_id for predictable diffs.
    out.sort(key=lambda e: e["pretalx_id"])
    return out


def merge_with_existing(new_entries: list[dict], existing_path: Path) -> list[dict]:
    """If a previous YAML exists, preserve fields the script doesn't own.

    Owned by the script (always overwritten from disk state):
      type, role, name, editions, default avatar image entry.

    Preserved verbatim from the existing YAML:
      any extra image entries beyond the auto-generated avatar,
      any extra top-level fields per entry,
      any commentary fields.
    """
    if not existing_path.exists():
        return new_entries
    try:
        existing = yaml.safe_load(existing_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        print(f"warning: existing {existing_path} is not valid YAML — overwriting", file=sys.stderr)
        return new_entries
    old_entries = {e["pretalx_id"]: e for e in (existing.get("entries") or []) if "pretalx_id" in e}

    merged = []
    for e in new_entries:
        old = old_entries.get(e["pretalx_id"])
        if not old:
            merged.append(e)
            continue
        # Preserve any image entries the script didn't generate.
        auto_paths = {img["path"] for img in e["images"]}
        extra_images = [img for img in (old.get("images") or [])
                        if img.get("path") not in auto_paths]
        e["images"].extend(extra_images)
        # Preserve any extra top-level fields (e.g. a hand-added `notes`).
        for k, v in old.items():
            if k not in e and k not in {"images"}:
                e[k] = v
        merged.append(e)
    return merged


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=OUT, help="Output YAML path")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    by_code = walk_speakers()
    new_entries = to_entries(by_code)
    merged = merge_with_existing(new_entries, args.out)

    doc = OrderedDict()
    doc["# generated"] = (
        "Generated by utils/inventory_speaker_images.py. "
        "Re-running preserves hand-added fields and extra image entries."
    )
    doc["entries"] = merged

    # Convert OrderedDicts to plain dicts so pyyaml dumps cleanly.
    def to_plain(o):
        if isinstance(o, OrderedDict):
            return {k: to_plain(v) for k, v in o.items()}
        if isinstance(o, dict):
            return {k: to_plain(v) for k, v in o.items()}
        if isinstance(o, list):
            return [to_plain(v) for v in o]
        return o

    body = yaml.safe_dump(
        to_plain({"entries": merged}),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    )
    header = (
        "# Asset inventory of speaker images, keyed by Pretalx code.\n"
        "#\n"
        "# Schema: each entry is a person playing the `speaker` role with\n"
        "# one or more images. Re-runnable via\n"
        "#   uv run python utils/inventory_speaker_images.py\n"
        "# Hand-added fields and extra image entries are preserved on\n"
        "# re-run (matched per pretalx_id). Future roles (organiser,\n"
        "# sponsor contact, …) can land in this same file by adding\n"
        "# entries with a different `role:` value.\n"
        "\n"
    )
    text = header + body

    n_people = len(merged)
    n_images = sum(len(e.get("images", [])) for e in merged)
    n_editions = sum(len(e.get("editions", [])) for e in merged)

    if args.dry_run:
        print(text[:2000])
        print(f"... ({len(text)} bytes total)")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")

    print()
    print(f"  people:   {n_people}")
    print(f"  images:   {n_images}")
    print(f"  edition references: {n_editions}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
