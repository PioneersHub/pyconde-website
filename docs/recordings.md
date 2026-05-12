# YouTube recordings

Linking session recordings from a YouTube playlist into the matching talk pages. The sync is one-way (YouTube → repo) and idempotent.

## Inputs

- `databags/recordings.yaml` — per-edition playlist URLs and per-talk overrides.
- A YouTube Data API v3 key in `.env` as `YOUTUBE_API_KEY`.

`recordings.yaml` shape:

```yaml
editions:
  2025:
    playlists:
      - https://www.youtube.com/playlist?list=PL...
    # Override entries land here when fuzzy matching fails or attribution
    # was wrong. Key by Pretalx code.
    overrides:
      3VYSMS: OcGxDWNXPHU              # Pretalx code → YouTube video id
```

For older editions whose video titles do not carry the Pretalx code hashtag (2018–2024), the importer falls back to fuzzy title matching. Hit rate runs 75–93% — anything below the confidence threshold becomes an `overrides:` entry.

## Run a sync

```bash
uv run python utils/sync_recordings.py --year 2025
```

For batch runs across editions, pass `--year all`. The script:

1. Walks each edition's playlist and pulls video metadata (title, duration, thumbnail, published-at, video id).
2. Matches videos to talks — preferring an explicit `overrides:` entry, then exact-code-in-title, then fuzzy title match.
3. Writes the match into each talk's `contents.lr`:
   - `youtube_id`, `video_link`, `video_thumbnail`
   - `video_duration_iso` (ISO 8601 — `PT45M22S`)
   - `video_published_at`
   - `recording_available: yes`
4. Reports unmatched videos and unrecorded talks at the end so gaps can be patched via `overrides:`.

Rate-limit etiquette: the YouTube API quota is shared with other tooling. The script throttles between requests and caches video metadata locally — re-runs with no override changes hit the API only for diffs.

## Verifying the result

A recorded talk page renders:

- An inline `<iframe src="https://www.youtube-nocookie.com/embed/{id}">`.
- A `VideoObject` JSON-LD block referencing the talk's `Event` via `isPartOf`.
- A `▶ Recording` badge on the talk list and on speaker pages.
- A `<video:video>` entry in the video sitemap segment (see [docs/seo.md](seo.md)).

Talks with `do_not_record: yes` are skipped — no video, no transcript section, no schema video record — regardless of what the playlist contains.

## Common follow-ups

| Symptom | Fix |
|---|---|
| Right talk, wrong video | Add an `overrides:` entry mapping the Pretalx code to the correct video id |
| Video in YouTube but not on the talk page | Run `--year YYYY` again; check the unmatched-videos report at the end |
| Title spelling diverges from Pretalx, fuzzy match misses | Bump confidence threshold via `--fuzzy-cutoff 0.8` (default 0.6) or add an explicit override |
| Pre-roll / outro got merged into a single video covering multiple talks | Out of scope — add overrides per talk pointing to YouTube `&t=` deep-link timecodes manually |
