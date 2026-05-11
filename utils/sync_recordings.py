"""YouTube -> Lektor recording sync for confirmed talks.

Walks the per-edition YouTube playlists configured in
`databags/recordings.yaml`, matches videos to Pretalx talks by
hashtag in the description (e.g. "#LPUC9T"), and writes back the
youtube_id / video_link / video_published_at / video_duration_iso /
video_thumbnail / recording_available fields into each talk's
`content/talks/{code}/contents.lr`.

Modes:
* `--mode api`         (default): use YouTube Data API v3 via
                       `YOUTUBE_API_KEY` env var. Override map in
                       recordings.yaml still wins.
* `--mode override`    skip the API entirely; only apply explicit
                       overrides from recordings.yaml. Useful before
                       the API key is provisioned.

Respects do_not_record: a talk where the .lr file has
`do_not_record: yes` is left untouched (no video fields written).

Throttling: every API call is followed by a small sleep so we never
exceed YouTube's per-second quota. The full sync of one ~150-talk
edition stays well under the default 10k-units/day quota.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Iterable

import httpx
import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDINGS_CONFIG = REPO_ROOT / "databags" / "recordings.yaml"
PRETALX_CONFIG = REPO_ROOT / "databags" / "pretalx.yaml"
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
REQUEST_DELAY_S = 0.4  # ~2.5 req/s — safely under YouTube's default
MAX_PER_PAGE = 50

# Pretalx codes are 6 uppercase alphanumerics.
PRETALX_HASHTAG = re.compile(r"#([A-Z0-9]{6})\b")


def load_recordings_config() -> dict:
    with RECORDINGS_CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_youtube_api_key() -> str | None:
    load_dotenv(REPO_ROOT / ".env", override=False)
    return os.environ.get("YOUTUBE_API_KEY")


def iter_playlist_videos(playlist_id: str, api_key: str) -> Iterable[dict[str, Any]]:
    """Yield {videoId, title, description, publishedAt} for every entry in a playlist."""
    page_token: str | None = None
    while True:
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": MAX_PER_PAGE,
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token
        url = f"{YOUTUBE_API}/playlistItems?{urllib.parse.urlencode(params)}"
        r = httpx.get(url, timeout=30)
        if r.status_code == 403:
            raise SystemExit(f"YouTube API 403 for playlist {playlist_id}: {r.text[:200]}")
        r.raise_for_status()
        data = r.json()
        for item in data.get("items", []):
            sn = item["snippet"]
            yield {
                "videoId": sn.get("resourceId", {}).get("videoId"),
                "title": sn.get("title", ""),
                "description": sn.get("description", ""),
                "publishedAt": sn.get("publishedAt", ""),
            }
        page_token = data.get("nextPageToken")
        if not page_token:
            return
        time.sleep(REQUEST_DELAY_S)


def fetch_video_details(video_ids: list[str], api_key: str) -> dict[str, dict]:
    """Return {videoId: {duration_iso, thumbnail}} for the given video IDs."""
    out: dict[str, dict] = {}
    for i in range(0, len(video_ids), MAX_PER_PAGE):
        chunk = video_ids[i : i + MAX_PER_PAGE]
        params = {
            "part": "contentDetails,snippet",
            "id": ",".join(chunk),
            "key": api_key,
        }
        url = f"{YOUTUBE_API}/videos?{urllib.parse.urlencode(params)}"
        r = httpx.get(url, timeout=30)
        r.raise_for_status()
        for item in r.json().get("items", []):
            vid = item["id"]
            sn = item.get("snippet", {})
            thumbs = sn.get("thumbnails", {})
            best = thumbs.get("maxres") or thumbs.get("standard") or thumbs.get("high") or {}
            out[vid] = {
                "duration_iso": item.get("contentDetails", {}).get("duration", ""),
                "thumbnail": best.get("url", f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"),
                "published_at": sn.get("publishedAt", ""),
            }
        time.sleep(REQUEST_DELAY_S)
    return out


def extract_pretalx_code(text: str) -> str | None:
    m = PRETALX_HASHTAG.search(text or "")
    return m.group(1) if m else None


def build_code_to_video_map(cfg: dict, year: str, api_key: str | None) -> dict[str, dict]:
    """Combine API-discovered videos and explicit overrides into one map."""
    code_map: dict[str, dict] = {}

    # 1) API discovery (only if enabled and key present).
    api_enabled = cfg.get("api_enabled", True)
    playlists = (cfg.get("playlists", {}) or {}).get(year, {}) or {}
    if api_enabled and api_key:
        seen_videos: list[dict] = []
        for channel, playlist_id in playlists.items():
            if not playlist_id:
                continue
            print(f"  Walking {channel} playlist {playlist_id}…")
            for video in iter_playlist_videos(playlist_id, api_key):
                code = extract_pretalx_code(video["description"]) or extract_pretalx_code(
                    video["title"]
                )
                if code:
                    seen_videos.append((code, video))
            time.sleep(REQUEST_DELAY_S)

        if seen_videos:
            video_ids = [v["videoId"] for _, v in seen_videos if v["videoId"]]
            details = fetch_video_details(video_ids, api_key)
            for code, v in seen_videos:
                vid = v["videoId"]
                d = details.get(vid, {})
                code_map[code] = {
                    "youtube_id": vid,
                    "video_link": f"https://www.youtube.com/watch?v={vid}",
                    "video_published_at": (v.get("publishedAt") or "").split("T")[0],
                    "video_duration_iso": d.get("duration_iso", ""),
                    "video_thumbnail": d.get("thumbnail", ""),
                }

    # 2) Explicit overrides — always applied last so they win.
    # Supports year-keyed (overrides.{year}.{code}) and legacy flat
    # (overrides.{code}) layouts so the YAML can evolve without
    # breaking older entries.
    raw_overrides = cfg.get("overrides") or {}
    year_block = raw_overrides.get(year) or raw_overrides.get(str(year)) or {}
    flat_block = {
        k: v for k, v in raw_overrides.items()
        if not isinstance(v, dict) and k not in {str(y) for y in range(2000, 2100)}
    }
    overrides = {**flat_block, **year_block}  # year-keyed wins over flat

    override_video_ids: list[str] = []
    for code, vid in overrides.items():
        if not vid:
            continue
        code_map.setdefault(code, {}).update(
            {
                "youtube_id": vid,
                "video_link": f"https://www.youtube.com/watch?v={vid}",
                "video_thumbnail": f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
            }
        )
        override_video_ids.append(vid)

    # If the API key is available, fetch contentDetails for override-derived
    # IDs too (otherwise duration / upload_date stay empty). One API call per
    # 50 videos — well within quota even for the full 2024+2025+2026 set.
    if api_enabled and api_key and override_video_ids:
        print(f"  Fetching details for {len(override_video_ids)} overridden videos…")
        details = fetch_video_details(override_video_ids, api_key)
        # Reverse-lookup vid -> code to attach details.
        vid_to_code = {data["youtube_id"]: code for code, data in code_map.items() if data.get("youtube_id")}
        for vid, d in details.items():
            code = vid_to_code.get(vid)
            if not code:
                continue
            code_map[code].update(
                {
                    "video_duration_iso": d.get("duration_iso", ""),
                    "video_thumbnail": d.get("thumbnail", code_map[code].get("video_thumbnail", "")),
                    "video_published_at": (d.get("published_at") or "").split("T")[0] if d.get("published_at") else code_map[code].get("video_published_at", ""),
                }
            )

    return code_map


# Fields we own in the .lr file. Re-stamping a talk on every sync
# means we always overwrite stale data; missing keys are written empty.
VIDEO_FIELDS = (
    "youtube_id",
    "video_link",
    "video_published_at",
    "video_duration_iso",
    "video_thumbnail",
    "recording_available",
)


def read_lr_blocks(path: Path) -> list[tuple[str, str]]:
    """Parse a Lektor `contents.lr` file into [(key, value), ...] preserving order."""
    raw = path.read_text(encoding="utf-8")
    chunks = raw.split("\n---\n")
    blocks: list[tuple[str, str]] = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        # First line is "key:" (possibly with inline value); rest is value.
        head, _, tail = chunk.partition("\n")
        if ":" in head:
            key, _, inline = head.partition(":")
            value = inline.strip()
            if tail:
                value = (value + ("\n" if value else "") + tail).rstrip("\n")
            blocks.append((key.strip(), value))
    return blocks


def write_lr_blocks(path: Path, blocks: list[tuple[str, str]]) -> None:
    parts = []
    for key, value in blocks:
        if value and "\n" in value:
            parts.append(f"{key}:\n\n{value}")
        else:
            parts.append(f"{key}: {value}" if value else f"{key}:")
    path.write_text("\n---\n".join(parts) + "\n", encoding="utf-8")


def talks_dir_for_year(year: str) -> Path:
    """Resolve where talks for the given year live in the content tree.

    Mirrors utils/talks.py.talks_dir_for: current edition at /talks/,
    historical editions under /archive/{year}/talks/.
    """
    current_year = ""
    if PRETALX_CONFIG.exists():
        with PRETALX_CONFIG.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        current_year = str(cfg.get("events", {}).get("current", {}).get("year", ""))
    if year == current_year:
        return REPO_ROOT / "content" / "talks"
    return REPO_ROOT / "content" / "archive" / year / "talks"


def apply_to_talk_file(code: str, video: dict, year: str, dry_run: bool = False) -> str:
    """Write the discovered video fields into the talk's contents.lr.

    Skips and returns 'skip' if the talk is marked do_not_record.
    Returns 'updated' on successful write, 'unchanged' if values matched,
    'missing' if the talk dir does not exist.
    """
    talks_dir = talks_dir_for_year(year)
    lr_path = talks_dir / code / "contents.lr"
    if not lr_path.exists():
        return "missing"
    blocks = read_lr_blocks(lr_path)
    block_map = {k: v for k, v in blocks}

    if (block_map.get("do_not_record", "no").strip().lower() in {"yes", "true", "1"}):
        return "skip"

    new_values = {
        "youtube_id": video.get("youtube_id", ""),
        "video_link": video.get("video_link", ""),
        "video_published_at": video.get("video_published_at", ""),
        "video_duration_iso": video.get("video_duration_iso", ""),
        "video_thumbnail": video.get("video_thumbnail", ""),
        "recording_available": "yes" if video.get("youtube_id") else "no",
    }

    if all(block_map.get(k, "") == v for k, v in new_values.items()):
        return "unchanged"

    if dry_run:
        return "would-update"

    new_blocks: list[tuple[str, str]] = []
    seen_keys = set()
    for k, v in blocks:
        if k in new_values:
            new_blocks.append((k, new_values[k]))
            seen_keys.add(k)
        else:
            new_blocks.append((k, v))
    for k, v in new_values.items():
        if k not in seen_keys:
            new_blocks.append((k, v))

    write_lr_blocks(lr_path, new_blocks)
    return "updated"


def resolve_year(args_year: str | None) -> str:
    if args_year:
        return args_year
    # Fall back to events.current from databags/pretalx.yaml.
    pretalx_path = REPO_ROOT / "databags" / "pretalx.yaml"
    if pretalx_path.exists():
        with pretalx_path.open(encoding="utf-8") as f:
            pcfg = yaml.safe_load(f) or {}
        return str(pcfg.get("events", {}).get("current", {}).get("year", ""))
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync YouTube recordings into Lektor talks.")
    parser.add_argument("--year", help="Edition year to sync (defaults to events.current).")
    parser.add_argument(
        "--mode",
        choices=("api", "override"),
        default="api",
        help="api: use YouTube Data API; override: only apply manual overrides.",
    )
    parser.add_argument("--talk-code", help="Limit sync to a single talk code.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing files.",
    )
    args = parser.parse_args()

    cfg = load_recordings_config()
    year = resolve_year(args.year)
    if not year:
        raise SystemExit("Could not resolve target year. Pass --year or set events.current in databags/pretalx.yaml.")

    api_key = get_youtube_api_key() if args.mode == "api" else None
    if args.mode == "api" and not api_key:
        print("No YOUTUBE_API_KEY in env — falling back to override-only mode.")

    code_map = build_code_to_video_map(cfg, year, api_key)
    print(f"Discovered {len(code_map)} video↔code mappings for year {year}.")

    if args.talk_code:
        filtered = {args.talk_code: code_map[args.talk_code]} if args.talk_code in code_map else {}
        if not filtered:
            print(f"No video found for {args.talk_code}; nothing to do.")
            return
        code_map = filtered

    counts: dict[str, int] = {"updated": 0, "unchanged": 0, "skip": 0, "missing": 0, "would-update": 0}
    for code, video in sorted(code_map.items()):
        result = apply_to_talk_file(code, video, year, dry_run=args.dry_run)
        counts[result] = counts.get(result, 0) + 1
        if result in {"updated", "would-update", "skip", "missing"}:
            print(f"  {code}: {result}  {video.get('youtube_id','')}")

    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
