"""YouTube -> Lektor recording sync for confirmed talks.

Walks the per-edition YouTube playlists configured in
`databags/recordings.yaml`, matches videos to Pretalx talks by
hashtag in the description (e.g. "#LPUC9T"), and writes back the
youtube_id / video_link / video_published_at / video_duration_iso /
video_thumbnail / recording_available fields into each talk.

Where a talk lives: the current edition is at `content/talks/{slug}/`
and every other edition at `content/archive/{year}/talks/{slug}/`.
Folders are named by *slug*, not by Pretalx code — the code-named
sibling is a `_model: redirect` 301 stub written by
`migrate_pretalx_slugs.py`. Talks are therefore resolved through
`lektor_lr.build_code_index()`, which reads each talk's `code:` field
and skips redirects. Writing to a code-named folder would silently
destroy a redirect and publish a duplicate talk page; see the module
docstring of `utils/lektor_lr.py` for the full account.

Modes:
* `--mode api`         (default): use YouTube Data API v3 via
                       `YOUTUBE_API_KEY` env var. Override map in
                       recordings.yaml still wins.
* `--mode override`    skip the API entirely; only apply explicit
                       overrides from recordings.yaml. Useful before
                       the API key is provisioned. Note that this
                       leaves video_published_at and video_duration_iso
                       empty — those two come only from the API.

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
import time
import urllib.parse
from pathlib import Path
from typing import Any, Iterable

import httpx
import lektor_lr
import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDINGS_CONFIG = REPO_ROOT / "databags" / "recordings.yaml"
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


_TITLE_NORM_RE = re.compile(r"[^a-z0-9]+")


def normalize_title(text: str) -> str:
    """Lower-case, strip non-alphanumerics, collapse — a stable matching key."""
    if not text:
        return ""
    # Drop leading "PyConDE — " / "PyData …" channel-tag prefixes the YouTube
    # team often adds. The pretalx title is the canonical truth.
    stripped = re.sub(r"^(pycon\s*de|pyconde|pydata)[^a-z0-9]*", "", text.lower())
    return _TITLE_NORM_RE.sub("", stripped)


def load_pretalx_titles(year: str, current_year: str) -> dict[str, str]:
    """Return {pretalx_code: normalized_title} for the local talks of an edition.

    Reads the talks.json bag the importer wrote so we don't re-hit Pretalx.
    """
    bag_path = REPO_ROOT / "databags" / ("talks.json" if year == current_year else f"talks-{year}.json")
    if not bag_path.exists():
        return {}
    import json as _json
    data = _json.loads(bag_path.read_text())
    out = {}
    for talk in data.get("talks", []):
        code = talk.get("code")
        title = talk.get("title")
        if code and title:
            out[code] = normalize_title(title)
    return out


def fuzzy_match_by_title(video_title: str, pretalx_titles: dict[str, str]) -> str | None:
    """Match a YouTube title to a Pretalx code by normalized-title equality.

    First tries an exact normalized match. Then falls back to substring
    containment (either direction) — useful when the YouTube title prepends
    "Speaker Name — Talk Title" or appends a track tag.
    """
    norm_video = normalize_title(video_title)
    if not norm_video:
        return None
    # Exact-normalized match
    for code, norm in pretalx_titles.items():
        if norm and norm == norm_video:
            return code
    # Substring containment (one direction in either)
    candidates: list[tuple[int, str]] = []
    for code, norm in pretalx_titles.items():
        if not norm:
            continue
        if norm_video in norm or norm in norm_video:
            # Score by length of the shorter side (better signal than overlap).
            candidates.append((min(len(norm), len(norm_video)), code))
    if candidates:
        # Return the longest-overlap match — most distinctive.
        candidates.sort(reverse=True)
        return candidates[0][1]
    return None


def build_code_to_video_map(cfg: dict, year: str, api_key: str | None) -> dict[str, dict]:
    """Combine API-discovered videos and explicit overrides into one map."""
    code_map: dict[str, dict] = {}

    # 1) API discovery (only if enabled and key present).
    api_enabled = cfg.get("api_enabled", True)
    playlists = (cfg.get("playlists", {}) or {}).get(year, {}) or {}
    if api_enabled and api_key:
        seen_videos: list[tuple[str, dict, str]] = []  # (code, video, match_type)
        unmatched_videos: list[dict] = []
        for channel, playlist_id in playlists.items():
            if not playlist_id:
                continue
            print(f"  Walking {channel} playlist {playlist_id}…")
            for video in iter_playlist_videos(playlist_id, api_key):
                code = extract_pretalx_code(video["description"]) or extract_pretalx_code(
                    video["title"]
                )
                if code:
                    seen_videos.append((code, video, "hashtag"))
                else:
                    unmatched_videos.append(video)
            time.sleep(REQUEST_DELAY_S)

        # Fuzzy fallback for old editions where YouTube descriptions don't
        # carry a Pretalx hashtag — match the video title against the
        # importer's talks.json. Same-edition only; no cross-year matching.
        if unmatched_videos:
            pretalx_titles = load_pretalx_titles(year, lektor_lr.current_year())
            matched_codes = {c for c, _, _ in seen_videos}
            fuzzy_hits = 0
            for video in unmatched_videos:
                code = fuzzy_match_by_title(video["title"], pretalx_titles)
                if code and code not in matched_codes:
                    seen_videos.append((code, video, "fuzzy"))
                    matched_codes.add(code)
                    fuzzy_hits += 1
            if fuzzy_hits:
                print(f"  Fuzzy-title matched {fuzzy_hits} of {len(unmatched_videos)} hashtag-less videos.")

        if seen_videos:
            video_ids = [v["videoId"] for _, v, _ in seen_videos if v["videoId"]]
            details = fetch_video_details(video_ids, api_key)
            for code, v, _match_type in seen_videos:
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


def apply_to_talk_file(talk_dir: Path, video: dict, dry_run: bool = False) -> str:
    """Write the discovered video fields into the talk's contents.lr.

    `talk_dir` comes from `lektor_lr.build_code_index()`, so it is always a
    canonical slug folder and never a redirect stub.

    Skips and returns 'skip' if the talk is marked do_not_record.
    Returns 'updated' on successful write, 'unchanged' if values matched.
    """
    lr_path = talk_dir / "contents.lr"
    text, fields = lektor_lr.read_lr(lr_path)

    # Two guards that must never fire. The first would mean the code index
    # handed back a redirect stub; the second that the parser could not
    # reproduce the file, so a write could lose content it did not understand.
    # Either way, abort loudly rather than write something unverifiable.
    if lektor_lr.is_redirect(fields):
        raise SystemExit(f"Refusing to write: {lr_path} is a redirect stub.")
    if not lektor_lr.round_trip_ok(text, fields):
        raise SystemExit(f"Refusing to write: {lr_path} does not round-trip.")

    if (lektor_lr.field_value(fields, "do_not_record", "no") or "no").strip().lower() in {
        "yes",
        "true",
        "1",
    }:
        return "skip"

    # Built in the canonical field order used by every other edition, since
    # dict order determines where newly-added fields are appended.
    youtube_id = video.get("youtube_id", "")
    new_values = {"youtube_id": youtube_id}

    # Never blank an existing video_link. The 2016 edition's recordings are
    # hosted by LMU Munich and have a video_link but no youtube_id; an empty
    # incoming value must not wipe the only link those talks have.
    incoming_link = video.get("video_link", "")
    if incoming_link or not lektor_lr.field_value(fields, "video_link"):
        new_values["video_link"] = incoming_link

    new_values.update(
        {
            "video_published_at": video.get("video_published_at", ""),
            "video_duration_iso": video.get("video_duration_iso", ""),
            "video_thumbnail": video.get("video_thumbnail", ""),
            "recording_available": "yes" if youtube_id else "no",
        }
    )

    if all(lektor_lr.field_value(fields, k, "") == v for k, v in new_values.items()):
        return "unchanged"

    if dry_run:
        return "would-update"

    lektor_lr.upsert_fields(fields, new_values)
    lektor_lr.write_lr(lr_path, fields)
    return "updated"


def resolve_year(args_year: str | None) -> str:
    """Explicit --year wins; otherwise fall back to events.current."""
    return args_year or lektor_lr.current_year()


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
        "--codes",
        help="Comma-separated list of Pretalx codes to limit sync to (a batch).",
    )
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
    elif args.codes:
        wanted = {c.strip() for c in args.codes.split(",") if c.strip()}
        filtered = {c: v for c, v in code_map.items() if c in wanted}
        missing = sorted(wanted - set(code_map))
        if missing:
            print(f"  No video mapping for {len(missing)} batch code(s): {', '.join(missing)}")
        if not filtered:
            print("No batch codes matched a video; nothing to do.")
            return
        code_map = filtered

    talks_dir = lektor_lr.talks_dir_for_year(year)
    code_index = lektor_lr.build_code_index(talks_dir)
    print(f"Indexed {len(code_index)} talks by Pretalx code under {talks_dir}.")

    counts: dict[str, int] = {"updated": 0, "unchanged": 0, "skip": 0, "missing": 0, "would-update": 0}
    for code, video in sorted(code_map.items()):
        talk_dir = code_index.get(code)
        if talk_dir is None:
            counts["missing"] += 1
            print(f"  {code}: missing  (no talk with this code under {talks_dir})")
            continue
        result = apply_to_talk_file(talk_dir, video, dry_run=args.dry_run)
        counts[result] = counts.get(result, 0) + 1
        if result in {"updated", "would-update", "skip"}:
            # Print the resolved path: it is the only way a --dry-run can
            # prove which file a real run would write.
            rel = talk_dir.relative_to(REPO_ROOT)
            print(f"  {code}: {result}  {video.get('youtube_id','')}  -> {rel}/contents.lr")

    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
