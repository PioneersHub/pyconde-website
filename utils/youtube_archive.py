"""YouTube → Lektor importer for editions without Pretalx data.

For old conference years (2022, 2019, 2018) the Pretalx event isn't
available, so the YouTube playlists ARE the canonical record of what
was presented. This utility walks the configured playlists and writes
one talk page per video at:

    content/archive/{year}/talks/{video_id}/contents.lr

The pages reuse the standard `talk` model so the existing talk.html
template renders them — the Pretalx-specific fields (Python skill,
domain expertise, etc.) are left empty and the template's `{% if … %}`
guards already handle that.

Each edition also gets a `content/archive/{year}/contents.lr` and
`content/archive/{year}/talks/contents.lr` index stub created
idempotently.

Usage: `python utils/youtube_archive.py --year 2022` (or `--all`).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import textwrap
from pathlib import Path
from string import Template
from typing import Iterable

import yaml
from dotenv import load_dotenv

# Re-use YouTube playlist + details fetch from sync_recordings.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_recordings import (  # noqa: E402
    iter_playlist_videos,
    fetch_video_details,
    REQUEST_DELAY_S,
)
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDINGS_CONFIG = REPO_ROOT / "databags" / "recordings.yaml"
CONTENT_DIR = REPO_ROOT / "content"
META_DESCRIPTION_MAX = 155

# Editions that have only YouTube data (no Pretalx event reachable).
YT_ONLY_EDITIONS: dict[str, dict] = {
    "2022": {
        "title": "PyCon DE & PyData Berlin 2022",
        "date_from": "2022-04-11",
        "date_to": "2022-04-13",
        "location": "bcc Berlin Congress Center",
    },
    "2019": {
        "title": "PyCon DE & PyData Berlin 2019",
        "date_from": "2019-10-09",
        "date_to": "2019-10-11",
        "location": "Kosmos Berlin",
    },
    "2018": {
        "title": "PyCon DE & PyData Karlsruhe 2018",
        "date_from": "2018-10-24",
        "date_to": "2018-10-26",
        "location": "Karlsruhe",
    },
}


def load_recordings_config() -> dict:
    with RECORDINGS_CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_api_key() -> str:
    load_dotenv(REPO_ROOT / ".env", override=False)
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        raise SystemExit("YOUTUBE_API_KEY not set in .env")
    return key


def make_meta_description(text: str) -> str:
    if not text:
        return ""
    collapsed = re.sub(r"\s+", " ", text.strip())
    if len(collapsed) <= META_DESCRIPTION_MAX:
        return collapsed
    return textwrap.shorten(collapsed, width=META_DESCRIPTION_MAX, placeholder="…")


# Matches the standard talks.py LR_TEMPLATE shape so the talk.html
# template finds every expected field, even when the value is empty.
LR_TEMPLATE = Template("""title: $title
---
description: $description
---
created: $created
---
code: $code
---
speaker_names: $speaker_names
---
speakers:

$speakers
---
abstract:

$abstract
---
full_description:

$full_description
---
room: $room
---
day: $day
---
slot_date: $slot_date
---
start_time: $start_time
---
end_time: $end_time
---
slot_id: $slot_id
---
track: $track
---
tags:

$tags
---
submission_type: $submission_type
---
submission_type_label: $submission_type_label
---
submission_type_id: $submission_type_id
---
is_keynote: $is_keynote
---
do_not_record: $do_not_record
---
streaming_consent: $streaming_consent
---
already_recorded: $already_recorded
---
python_skill: $python_skill
---
domain_expertise: $domain_expertise
---
supporting_material_url: $supporting_material_url
---
slides_link: $slides_link
---
social_card_image: $social_card_image
---
youtube_id: $youtube_id
---
video_link: $video_link
---
video_published_at: $video_published_at
---
video_duration_iso: $video_duration_iso
---
video_thumbnail: $video_thumbnail
---
recording_available: $recording_available
""")


def video_to_lr(video: dict, details: dict, year: str) -> str:
    """Render a single YouTube video as a Lektor talk page."""
    vid = video["videoId"]
    title = video["title"].strip()
    description = (video.get("description") or "").strip()
    abstract = textwrap.shorten(description, width=600, placeholder="…") if description else ""
    published = (video.get("publishedAt") or "").split("T")[0]
    thumb = details.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
    duration = details.get("duration_iso") or ""

    fields = {
        "title": title,
        "description": make_meta_description(description) or title,
        "created": published or f"{year}-01-01",
        "code": vid,
        "speaker_names": "",
        "speakers": "",
        "abstract": abstract,
        "full_description": description,
        "room": "",
        "day": "",
        "slot_date": "",
        "start_time": "",
        "end_time": "",
        "slot_id": "",
        "track": "",
        "tags": "",
        "submission_type": "talk_short",
        "submission_type_label": "Talk",
        "submission_type_id": "",
        "is_keynote": "no",
        "do_not_record": "no",
        "streaming_consent": "yes",
        "already_recorded": "no",
        "python_skill": "",
        "domain_expertise": "",
        "supporting_material_url": "",
        "slides_link": "",
        "social_card_image": thumb,
        "youtube_id": vid,
        "video_link": f"https://www.youtube.com/watch?v={vid}",
        "video_published_at": published,
        "video_duration_iso": duration,
        "video_thumbnail": thumb,
        "recording_available": "yes",
    }
    return LR_TEMPLATE.substitute(fields)


def write_edition_stub(year: str, meta: dict, talk_count: int) -> None:
    """Create the edition + talks listing pages idempotently."""
    edition_dir = CONTENT_DIR / "archive" / year
    edition_dir.mkdir(parents=True, exist_ok=True)
    (edition_dir / "contents.lr").write_text(
        f"""_model: archive-edition
---
title: {meta['title']}
---
year: {year}
---
date_from: {meta['date_from']}
---
date_to: {meta['date_to']}
---
location: {meta['location']}
---
pretalx_slug:
---
talk_count: {talk_count}
---
body:

The {year} edition of PyCon DE & PyData. The original Pretalx programme
is not preserved here, so this archive surfaces the {talk_count}
recorded sessions directly from the YouTube playlist. Browse the
[archived talks](talks/) below.
""",
        encoding="utf-8",
    )
    talks_dir = edition_dir / "talks"
    talks_dir.mkdir(parents=True, exist_ok=True)
    (talks_dir / "contents.lr").write_text(
        f"_model: talks\n---\ntitle: {meta['title']} — Talks\n",
        encoding="utf-8",
    )


def remove_old_talks(talks_dir: Path) -> None:
    if not talks_dir.exists():
        return
    for entry in talks_dir.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)


def videos_for_year(year: str, cfg: dict, api_key: str) -> Iterable[tuple[dict, dict]]:
    """Walk all configured playlists for `year` and yield (video, details)."""
    playlists = (cfg.get("playlists") or {}).get(year) or {}
    collected: list[dict] = []
    seen_ids: set[str] = set()
    for channel, playlist_id in playlists.items():
        if not playlist_id:
            continue
        print(f"  Walking {channel} playlist {playlist_id}…")
        for video in iter_playlist_videos(playlist_id, api_key):
            vid = video.get("videoId")
            if not vid or vid in seen_ids:
                continue
            seen_ids.add(vid)
            collected.append(video)
        time.sleep(REQUEST_DELAY_S)

    if not collected:
        return
    print(f"  Fetching contentDetails for {len(collected)} videos…")
    details = fetch_video_details([v["videoId"] for v in collected], api_key)
    for v in collected:
        yield v, details.get(v["videoId"], {})


def import_year(year: str, cfg: dict, api_key: str, keep_existing: bool = False) -> int:
    meta = YT_ONLY_EDITIONS.get(year)
    if not meta:
        print(f"  No edition meta for {year} — skipping.")
        return 0
    talks_dir = CONTENT_DIR / "archive" / year / "talks"
    if not keep_existing:
        remove_old_talks(talks_dir)
    talks_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for video, details in videos_for_year(year, cfg, api_key):
        vid = video["videoId"]
        rendered = video_to_lr(video, details, year)
        (talks_dir / vid).mkdir(parents=True, exist_ok=True)
        (talks_dir / vid / "contents.lr").write_text(rendered, encoding="utf-8")
        count += 1

    if count:
        write_edition_stub(year, meta, count)
        print(f"  → {count} talks written to {talks_dir}")
    else:
        print(f"  → no videos for {year}, edition not created")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Import YouTube-only conference editions into Lektor.")
    parser.add_argument("--year", help="Single year to import (2022/2019/2018).")
    parser.add_argument("--all", action="store_true", help="Import every YouTube-only year defined in this script.")
    parser.add_argument("--keep-existing", action="store_true", help="Skip the wipe of talks/ before reimport.")
    args = parser.parse_args()

    cfg = load_recordings_config()
    api_key = get_api_key()

    if args.all:
        years = list(YT_ONLY_EDITIONS.keys())
    elif args.year:
        years = [args.year]
    else:
        raise SystemExit("Pass --year YYYY or --all")

    for year in years:
        print(f"\n== Importing {year} ==")
        import_year(year, cfg, api_key, keep_existing=args.keep_existing)


if __name__ == "__main__":
    main()
