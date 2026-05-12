# YouTube recordings

Two flows:

1. **Link** existing YouTube videos to talk pages — one-way YouTube → repo, idempotent.
2. **Download** the audio of every linked video so the audio can be fed into the transcription pipeline ([docs/transcripts.md](transcripts.md)).

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

## Audio downloads for the transcription pipeline

After the YouTube sync has populated `youtube_id` fields, the audio of every linked recording can be batch-downloaded as m4a for the transcription pipeline.

```bash
uv run python utils/download_audio.py --year 2023
uv run python utils/download_audio.py --year all          # every archived edition
uv run python utils/download_audio.py --year 2023 --dry-run
```

Defaults:

- Destination: `~/Documents/Claude/{year}-audio/` (mirrors the convention the transcription pipeline already reads).
- Filename: `{CODE}-{slug}.m4a` — `{slug}` is the talk's frozen slug from `contents.lr`, or a freshly slugified title if no slug field is present.
- Format: `bestaudio[ext=m4a]/bestaudio` — picks the m4a-native stream YouTube serves; falls back to the best audio-only stream if m4a isn't on offer.

Behaviour:

- Talks with no `youtube_id` or `do_not_record: yes` are skipped silently.
- Existing files are skipped — re-running the script resumes only failed or new downloads.
- A `_download_log.txt` is appended in each year's audio folder.
- Per-talk failures are reported at the end with the error tail; the script exits non-zero so CI / wrappers can react.
- `ffmpeg` is not strictly required (m4a-native streams transfer as-is). If yt-dlp needs to merge formats and ffmpeg is missing, the script logs a hint at startup; install ffmpeg or pass a stricter format selector.

Size estimate: ~15–25 MB per 30-minute talk. A full edition runs 1–3 GB and 1–3 hours wall-clock depending on network — start in the background or pick a specific year.

Once a year's audio is on disk, hand the folder to the transcription pipeline; the outputs land back under `~/Documents/Claude/{year}-transcripts/` for [docs/transcripts.md](transcripts.md) to ingest.
