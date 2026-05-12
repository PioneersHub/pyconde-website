# Archive

Every prior edition lives under `/archive/{year}/`. The structure mirrors the current edition and stays stable across re-imports, so external links to old talks and speakers never break.

## URL layout

```text
/archive/                                            # edition index
/archive/{year}/                                     # one edition (Event JSON-LD, EventCompleted)
/archive/{year}/talks/                               # talk list for that edition
/archive/{year}/talks/{slug}/                        # one talk (canonical)
/archive/{year}/talks/{CODE}/                        # 301 redirect → slug URL (HTML meta-refresh + canonical)
/archive/{year}/speakers/                            # speaker list
/archive/{year}/speakers/{CODE}/                     # one speaker (Person JSON-LD)
/archive/{year}/tracks/                              # track index for the edition
/archive/{year}/tracks/{slug}/                       # talks in one track (CollectionPage JSON-LD)
```

Slugs are derived from titles at migration time and frozen in each talk's `contents.lr` (`slug:` field). Pretalx codes remain the stable internal identifier — speakers still reference talks by code, and the redirect from `/talks/{CODE}/` to `/talks/{slug}/` keeps any externally-shared code URL working.

Editions currently archived: 2018, 2019, 2022, 2023, 2024, 2025. (Gap years had no PyCon DE.)

## Anatomy of an archived talk

A talk's `content/archive/{year}/talks/{slug}/contents.lr` carries:

| Field | Source | Notes |
|---|---|---|
| `code` | Pretalx | Immutable Pretalx submission code, used for cross-references |
| `slug` | derived | Slugified title; frozen after first migration |
| `title`, `abstract`, `description`, `track`, `room`, `day`, `start_time`, `duration` | Pretalx | Re-imports overwrite |
| `youtube_id`, `video_link`, `video_thumbnail`, `video_duration_iso`, `recording_available` | YouTube sync | See [docs/recordings.md](recordings.md) |
| `transcript`, `transcript_status`, `transcript_language` | transcript import | See [docs/transcripts.md](transcripts.md) |
| `do_not_record` | Pretalx | Suppresses both video embed and transcript display |

Speakers list talks by **slug** (post-migration). Talks list speakers via the speakers index (lookup by Pretalx code stored on the speaker record).

## Common tasks

| Task | Doc |
|---|---|
| Re-import speakers or talks from Pretalx for an archived year | [docs/pretalx.md](pretalx.md) (use `--year YYYY` on the importer) |
| Link more YouTube recordings to an archived edition | [docs/recordings.md](recordings.md) |
| Import transcripts for a previously-skipped edition | [docs/transcripts.md](transcripts.md) |
| Regenerate track pages after the talks list changed | `uv run python utils/generate_tracks.py` |
| Add a Pretalx-code redirect after renaming a slug | `uv run python utils/migrate_pretalx_slugs.py` (idempotent) |
| Add a manual /old/ → /new/ redirect | [docs/redirects.md](redirects.md) |
| Verify cross-edition speaker continuity | speaker.html iterates each year's `/speakers/{CODE}/`; same Pretalx code in multiple years renders the "Also at PyCon DE & PyData" card |

## Cross-edition integrity

A few invariants the build relies on:

- Pretalx codes are unique within a single edition but **not stable across editions** — Pretalx mints fresh codes per event. The "Also at" card on a speaker page therefore only catches direct code matches (which Pretalx does sometimes preserve when a speaker re-applies through the same account). A `databags/speaker_aliases.yaml` to bridge non-matching codes is an open item — see [docs/seo-crosslinking-concept.md](seo-crosslinking-concept.md) §7.
- Track names drift between editions ("DevOps" → "DevOps & MLOps" → "MLOps & DevOps"). Each edition's track index is its own page; tracks are not merged across years.
- Slug URLs are immutable. If a talk title changes after the slug is committed, the slug stays — preventing 404s. The displayed title updates normally.

## Adding a previously-skipped edition

The 2020 and 2021 editions don't exist (cancelled / online-only). If a prior edition needs to be added retroactively:

1. Provide a Pretalx event slug; record it in `databags/pretalx.yaml` under that year alongside the year-specific question and submission-type IDs.
2. Run `uv run python utils/talks.py --year YYYY` and `uv run python utils/speakers.py --year YYYY`.
3. Run the slug migration to produce slug URLs + Pretalx-code redirects: `uv run python utils/migrate_pretalx_slugs.py`.
4. Run track generation: `uv run python utils/generate_tracks.py`.
5. Optional: import transcripts and link recordings — same workflow as a post-conference cutover.
6. Add the edition to the footer year row in `templates/layout.html` and to `databags/past_editions.yaml` (homepage card).
