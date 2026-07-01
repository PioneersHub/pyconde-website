# After the conference

The hand-off window between the closing keynote and the moment the edition becomes part of the archive. Three operational threads run in parallel; they can be tackled in any order.

## Thread 1 — Recordings

YouTube uploads typically lag the event by 4–8 weeks. Once the post-production team finishes a batch, link the recordings to talk pages.

| Step | Doc |
|---|---|
| Sync recordings from a YouTube playlist | [docs/recordings.md](recordings.md) |
| Override / patch individual matches | [docs/recordings.md#recordings-yaml](recordings.md) |
| Re-run social-card generation if new keynote artwork dropped | `make sponsor-pages` is sponsor-only; for talk social cards run `uv run python utils/social_card_img_gen.py` |

A talk with a linked recording gets the YouTube embed on the talk page, a `recording_available: yes` flag, a `VideoObject` JSON-LD record, and an entry in the video sitemap.

## Thread 2 — Transcripts

Auto-generated from the recording audio, then imported into the talk's `contents.lr`. Once present, transcripts unlock per-talk full-text search and inflate the searchable corpus considerably (~14k lines for a typical edition).

| Step | Doc |
|---|---|
| Import a batch from a local directory | [docs/transcripts.md](transcripts.md) |
| Format spec (Speaker 1 / Speaker 2 diarization, panel speaker_map) | [docs/transcripts.md#format](transcripts.md) |

The importer is idempotent — re-running it on already-imported talks refreshes the field rather than appending.

## Thread 3 — Front page after the event

The site has **one always-conference front page** (no recap/inactive
mode, no activate/disable switch). When the conference closes, do
**not** flip the homepage to a recap state — instead:

- Publish the gratitude recap ("year in numbers", photos, thank-you)
  as **blog posts** and link them from the homepage `programme_status`
  band (`databags/fp_programme_status.yaml`) for a short while.
- Move the closing edition under `/archive/{year}/` (see the cutover
  steps below) so its content lives in the archive.
- Once the next edition's dates lock, update the front-page configs
  (`databags/fp_*.yaml`, `databags/homepage.yaml`) and
  `databags/site_state.yaml` to the next conference. The persistent
  archive funnel-CTA reads `site_state.yaml` and will point archive
  traffic at the new conference automatically.

Front-page config details: [docs/landing_pages.md](landing_pages.md).

## Cutover to the archive

When the next edition's site goes live, the current edition moves under `/archive/{year}/`. Sequence:

1. **Final Pretalx pull.** Run the importer one more time to capture late changes to bios or session metadata. See [docs/pretalx.md](pretalx.md).
2. **Recordings + transcripts complete.** Everything you want crawlable should be in by this point — once a page lives under `/archive/`, it inherits `EventCompleted` and `eventStatus` flips in JSON-LD.
3. **Move content.** Rename `content/talks/` to `content/archive/{year}/talks/` and `content/speakers/` to `content/archive/{year}/speakers/`. Create `content/archive/{year}/contents.lr` from a previous edition as a template.
4. **Re-generate derived content.**
   ```bash
   uv run python utils/migrate_pretalx_slugs.py    # slug URLs + Pretalx-code redirects
   uv run python utils/generate_tracks.py          # per-track index pages
   make build                                       # everything else (sitemaps, search, redirects)
   ```
   Both generator scripts are idempotent — they're safe to re-run on already-migrated content.
5. **Verify.** Pick three random talks, check the slug URL renders, the Pretalx code URL redirects, and the speaker page lists them. Crawl the new edition with the local static server (see [docs/search.md](search.md)) to confirm internal links resolve.

The archive layout and conventions are documented in [docs/archive.md](archive.md).
