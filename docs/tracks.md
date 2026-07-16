# Track index pages

Per-track collection pages — one per `track` value found across talks — generated from talk content at build time. Each gives crawlers a topical hub that aggregates every talk in that track, with `CollectionPage` JSON-LD referencing each `Event` via its stable `@id`.

## URL layout

```text
/tracks/                                  # current edition's track index
/tracks/{slug}/                           # one track for the current edition
/archive/{year}/tracks/                   # archived edition's track index
/archive/{year}/tracks/{slug}/            # one track for an archived edition
```

Slugs are derived from the track label via the same NFKD → ascii → lowercase → non-alnum → `-` pipeline used for talk slugs.

## Generate

```bash
make tracks
# equivalent to:
uv run python utils/generate_tracks.py
```

The script:

1. For each edition (`content/talks/` and every `content/archive/{year}/talks/`), reads the `track:` field from every talk's `contents.lr`.
2. Slugifies and groups by track label.
3. Replaces the contents of the corresponding `content/.../tracks/` directory with:
   - `contents.lr` (`_model: tracks`) — the edition's track index.
   - `{slug}/contents.lr` (`_model: track`) — one per track, declaring `name`, `slug`, `year`, `talk_count`.
4. Generated tracks are listed in `make build` output; cached files belong to the build, not to source control archaeology — re-run the generator instead of patching `contents.lr` by hand.

`make build` runs `make tracks` automatically so adding or removing a talk picks up its track entry on the next build.

## Templates

| Template | Renders |
|---|---|
| `templates/tracks.html` | Track index. Card grid keyed by track name, with talk counts; emits `CollectionPage` JSON-LD listing each track. |
| `templates/track.html` | One track. Re-queries the edition's talks (`talks_index.children`) and filters by `talk.track == this.name`, then renders a talk list with recording/transcript badges. Emits `CollectionPage` JSON-LD with `hasPart[]` pointing to each `Event` `@id`. |

The talks listing filters out `_model: redirect` siblings so Pretalx-code redirect pages don't appear in the listing.

## Cross-edition behaviour

Tracks are **not** merged across years. "MLOps & DevOps" in 2024 and "MLOps & DevOps" in 2025 are separate pages at separate URLs. Reasons:

- Track names drift between editions ("DevOps" → "DevOps & MLOps" → "MLOps & DevOps").
- Each per-edition track page acts as a frozen historical snapshot, with `CollectionPage` JSON-LD referencing that edition's `Event`.

If a cross-edition "Topic" hub is needed later (e.g. an evergreen `/topics/mlops/` page that aggregates every MLOps talk regardless of edition), introduce a curated `databags/topics.yaml` and a new template. The current per-edition tracks are kept simple intentionally.

## Common follow-ups

| Symptom | Fix |
|---|---|
| New talk added, track page doesn't show it | Run `make tracks` (or `make build`) — the track page is generated from talk content |
| Track page has zero talks | Source talk's `track:` field is blank or `None`; fix the field, re-run the importer or the generator |
| Two visibly-identical tracks because of a typo in one edition's labels ("Career" vs "Carreer") | Out of scope to auto-merge; fix the typo upstream in Pretalx and re-import, or accept that the historical edition keeps its label |
