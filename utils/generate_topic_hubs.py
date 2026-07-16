"""Generate cross-edition topic-hub pages from the talk archive.

`databags/topics.yaml` defines a `hubs` list (slug, title, matchers).
For each hub we scan every talk in the content tree — current edition
`content/talks/` plus every `content/archive/{year}/talks/` — match it
against the hub's keyword/track matchers, and write a standing
collection page at `content/topics/{slug}/` that aggregates the
matching talks across all editions.

The page itself only stores the matched talk URL paths; the template
(`templates/topic-hub.html`) resolves them via `site.get(...)` at
render time and emits `ItemList` + `BreadcrumbList` JSON-LD. This
keeps the generator decoupled from rendering and the .lr files small.

Idempotent: re-runs replace generated hub pages, leaving talk content
alone. Run via `make topic-hubs`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import yaml

REPO = Path(__file__).resolve().parent.parent
CONTENT = REPO / "content"
TOPICS_CONFIG = REPO / "databags" / "topics.yaml"
PRETALX_CONFIG = REPO / "databags" / "pretalx.yaml"
TOPICS_DIR = CONTENT / "topics"


def current_year() -> str:
    if PRETALX_CONFIG.exists():
        cfg = yaml.safe_load(PRETALX_CONFIG.read_text(encoding="utf-8")) or {}
        return str(cfg.get("events", {}).get("current", {}).get("year", ""))
    return ""


def parse_lr(text: str) -> dict[str, str]:
    """Parse a Lektor contents.lr into {key: value} (value is the raw block body)."""
    out: dict[str, str] = {}
    for chunk in text.split("\n---\n"):
        if not chunk.strip():
            continue
        head, _, tail = chunk.partition("\n")
        if ":" not in head:
            continue
        key, _, inline = head.partition(":")
        value = inline.strip()
        if tail:
            value = (value + ("\n" if value else "") + tail).rstrip("\n")
        out[key.strip()] = value
    return out


def talk_matches(parsed: dict[str, str], hub: dict) -> bool:
    keywords = [k.lower() for k in (hub.get("matchers") or {}).get("keywords") or []]
    tracks = [t.lower() for t in (hub.get("matchers") or {}).get("tracks") or []]
    title = (parsed.get("title") or "").lower()
    abstract = (parsed.get("abstract") or "").lower()
    track = (parsed.get("track") or "").lower()
    haystack = f"{title}\n{abstract}"
    if any(k and k in haystack for k in keywords):
        return True
    if track and any(t and t in track for t in tracks):
        return True
    return False


def iter_talks() -> Iterable[tuple[str, str, Path, dict[str, str]]]:
    """Yield (year, code, lr_path, parsed) for every talk in the content tree."""
    cur_year = current_year()
    cur_talks = CONTENT / "talks"
    if cur_talks.is_dir():
        for talk in sorted(cur_talks.iterdir()):
            lr = talk / "contents.lr"
            if lr.exists():
                parsed = parse_lr(lr.read_text(encoding="utf-8"))
                if parsed.get("_model") == "redirect":
                    continue
                yield (cur_year, talk.name, lr, parsed)
    archive = CONTENT / "archive"
    if archive.is_dir():
        for year_dir in sorted(archive.iterdir()):
            if not (year_dir.is_dir() and year_dir.name.isdigit()):
                continue
            talks = year_dir / "talks"
            if not talks.is_dir():
                continue
            for talk in sorted(talks.iterdir()):
                lr = talk / "contents.lr"
                if lr.exists():
                    parsed = parse_lr(lr.read_text(encoding="utf-8"))
                    if parsed.get("_model") == "redirect":
                        continue
                    yield (year_dir.name, talk.name, lr, parsed)


def talk_url_path(year: str, code: str, parsed: dict[str, str]) -> str:
    """Resolve the public URL path for a talk folder."""
    if year and year == current_year():
        root = "/talks"
    elif year:
        root = f"/archive/{year}/talks"
    else:
        root = "/talks"
    return f"{root}/{code}/"


def write_hub_page(hub: dict, talk_paths: list[str]) -> Path:
    slug = hub["slug"]
    hub_dir = TOPICS_DIR / slug
    hub_dir.mkdir(parents=True, exist_ok=True)
    title = hub.get("title") or hub.get("section_title") or slug
    description = hub.get("description") or ""
    # Lektor `strings` serializes as: key, blank line, then one value
    # per line (NO YAML `- ` prefix) — matches how speaker `talks:`
    # lists are stored.
    if talk_paths:
        paths_block = "talk_paths:\n\n" + "\n".join(talk_paths)
    else:
        paths_block = "talk_paths:"
    body = (
        "_model: topic-hub\n"
        "---\n"
        f"title: {title}\n"
        "---\n"
        f"slug: {slug}\n"
        "---\n"
        f"description: {description}\n"
        "---\n"
        f"talk_count: {len(talk_paths)}\n"
        "---\n"
        f"{paths_block}\n"
    )
    out = hub_dir / "contents.lr"
    out.write_text(body, encoding="utf-8")
    return out


def write_topics_index(hubs: list[dict]) -> Path:
    TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    body = (
        "_model: topics\n"
        "---\n"
        "title: Topics\n"
    )
    out = TOPICS_DIR / "contents.lr"
    out.write_text(body, encoding="utf-8")
    return out


def clear_hubs() -> None:
    if not TOPICS_DIR.is_dir():
        return
    for child in TOPICS_DIR.iterdir():
        if child.is_dir():
            for f in child.rglob("*"):
                if f.is_file():
                    f.unlink()
            child.rmdir()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    cfg = yaml.safe_load(TOPICS_CONFIG.read_text(encoding="utf-8")) or {}
    hubs = cfg.get("hubs") or []
    if not hubs:
        print("No `hubs:` defined in databags/topics.yaml — nothing to do.")
        return 0

    # Pre-group talks by hub in one pass over the archive.
    matched: dict[str, list[tuple[str, str]]] = {h["slug"]: [] for h in hubs}
    for year, code, _lr, parsed in iter_talks():
        for hub in hubs:
            if talk_matches(parsed, hub):
                matched[hub["slug"]].append((year or "", code))

    if args.dry_run:
        for hub in hubs:
            paths = matched[hub["slug"]]
            print(f"  {hub['slug']:<25} {len(paths)} talks")
        return 0

    clear_hubs()
    write_topics_index(hubs)
    for hub in hubs:
        hits = matched[hub["slug"]]
        # Sort by year desc then code for stable output.
        hits.sort(key=lambda yc: (yc[0], yc[1]), reverse=True)
        # Re-resolve url paths from the (year, code) pairs.
        # We need parsed only for nothing else here; url path is derived.
        paths = [talk_url_path(y, c, {}) for (y, c) in hits]
        write_hub_page(hub, paths)
        print(f"  wrote {hub['slug']}: {len(paths)} talks -> content/topics/{hub['slug']}/")

    print(f"\ntopic hubs generated: {len(hubs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
