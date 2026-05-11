# Crosslinking & Site Search — Concept (UX + SEO)

A holistic plan to turn the existing per-page content (talks, speakers,
tracks, recordings, transcripts) into a navigable, link-dense graph that
both users and search engines can traverse efficiently.

Last update: 2026-05-11.

---

## 0. What we already have

| Entity         | Pages                                                            | JSON-LD                                                                                  |
|----------------|------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| Edition / Year | `/`, `/archive/`, `/archive/{year}/`                             | `Event`, `WebSite`, `Organization`                                                       |
| Talk           | `/talks/{code}/`, `/archive/{year}/talks/{code}/`                | `Event` (with `recordedIn`, `subjectOf` → VideoObject + transcript)                      |
| Speaker        | `/speakers/{code}/`, `/archive/{year}/speakers/{code}/`          | `Person` (with `performerIn[]` referencing talk `@id`s)                                  |
| Recording      | embedded on talk page                                            | `VideoObject` (with `transcript` URL)                                                    |
| Transcript     | inline `<details>` block on talk page                            | referenced via `#transcript` fragment from `Event.subjectOf` and `VideoObject.transcript` |

Existing cross-links:
- Talk page links to its speakers (anchor + JSON-LD `performer[]`).
- Speaker page lists their talks (anchor + JSON-LD `performerIn[]`).
- Archive index links to per-edition pages; per-edition pages have a sub-nav to /talks/ and /speakers/.
- Footer carries a year-pill row and an "All editions" CTA.

This is enough for "spider can find every page", but not enough for "user landing on one detail page can find related content without using the back button".

---

## 1. Goals

**UX**
- A user landing on any leaf page (talk / speaker / transcript) should always have ≥3 obvious next destinations.
- Discovery: a user reading one transcript should learn about other talks on the same topic, by the same speaker, in the same track, or in the same edition.
- Search must work on transcript content, not just titles.

**SEO**
- Increase internal-link density so PageRank flows to long-tail pages (individual talks, speakers).
- Add structured `BreadcrumbList` JSON-LD so SERP renders breadcrumbs.
- Expose new index pages (tracks, tags, search) that aggregate keyword-relevant clusters.
- Keep canonical URLs stable; new pages must be additive, never replace existing.

**Non-goals**
- A recommender system. We will not score similarity — only enumerate explicit relations (same speaker, same track, same edition, same submission_type).
- Manual curation. Every relation must be derivable from existing data fields.

---

## 2. Relation model

Every detail page has a fixed set of relations it can surface. The
template emits each section only if the relation has ≥1 result so we
don't leave empty boxes.

### Talk page

| Section                          | Source                                                  | Cap     |
|----------------------------------|---------------------------------------------------------|---------|
| Speakers (already exists)        | `my_speakers` (resolved from `speakers/{code}/talks[]`) | all     |
| More by this speaker             | other talks where this code's speakers appear           | 4 each  |
| Same track this edition          | other talks with `track == this.track and year == this.year` | 6  |
| Same track other editions        | talks with same track across `/archive/*/talks/`        | 4       |
| Same edition (recommended)       | random sample from `/archive/{year}/talks/`             | 3       |
| Has a transcript                 | inline `<details>` (already exists)                     | n/a     |
| Watch the recording on YouTube   | inline iframe + JSON-LD VideoObject (already exists)    | n/a     |

### Speaker page

| Section                       | Source                                                  | Cap |
|-------------------------------|---------------------------------------------------------|-----|
| Sessions at $year (existing)  | `this.talks[]`                                          | all |
| Other editions                | same speaker code present in another edition's speaker index | all years |
| Tracks they've spoken in      | union of `talk.track` across this speaker's talks       | n/a |

### Track page (new)

| Section          | Source                                                  |
|------------------|---------------------------------------------------------|
| All talks in track (current edition) | iterate /talks/ by `track`              |
| Past talks in track                  | iterate /archive/*/talks/ by `track`    |
| Speakers in track                    | derived from speakers of those talks    |

URL: `/tracks/{slug}/` and `/archive/{year}/tracks/{slug}/`. CollectionPage JSON-LD with hasPart linking each Event.

### Archive edition page (existing)

Already has Talks/Speakers sub-nav. Extend with:
- "Tracks at $year" — derived from set of `talk.track` in that edition.
- "Keynotes" — talks with `is_keynote: yes`.

---

## 3. SEO-grade additions

### Breadcrumbs

Every page gets a `<nav aria-label="Breadcrumb">` with `BreadcrumbList` JSON-LD:

```
Home → Archive → 2025 → Talks → {Title}
Home → Archive → 2025 → Speakers → {Name}
Home → Talks → {Title}     (current edition)
Home → Tracks → MLOps & DevOps
```

Visual breadcrumb appears below the topnav, JSON-LD goes in the head.

### Internal anchor text

- Replace generic "More info" / "Browse" with descriptive anchors using the entity name. ("All talks in MLOps & DevOps" not "more").
- Speaker links carry `rel="author"` (already done on talk page).
- Past-edition links carry `rel="archived"` so crawlers signal them as historical.

### Sitemap segmentation

Replace single `/sitemap.xml` with a sitemap index referencing
per-content-type sitemaps:

```
/sitemap.xml                 → index
/sitemaps/pages.xml          → top-level pages
/sitemaps/talks-current.xml
/sitemaps/talks-archive.xml
/sitemaps/speakers.xml
/sitemaps/tracks.xml
```

Reasons: easier to spot indexing problems per segment in Search Console;
each sub-sitemap stays under the 50k-URL limit forever.

### Canonical safety

- Track and tag pages on archived editions canonicalize to themselves
  (each year's track list is a distinct topical page).
- Pagination (if any) uses `rel="prev"` / `rel="next"`.

---

## 4. Site search (Pagefind)

### Why Pagefind

- Static, runs at build time, zero infra.
- WASM index, ~10 KB shards loaded on demand.
- Supports filters (year, track, has_recording, has_transcript) and sorts.
- Highlights matches inside long bodies — perfect for transcripts.

### What to index

| Region                       | Index? | Filter facet?       |
|------------------------------|--------|---------------------|
| Talk title                   | yes    | —                   |
| Talk abstract                | yes    | —                   |
| Talk full_description        | yes    | —                   |
| Talk transcript              | yes    | `has_transcript`    |
| Speaker name + bio           | yes    | —                   |
| Track label                  | yes    | `track`             |
| Year                         | meta   | `year`              |
| Has recording                | meta   | `has_recording`     |
| Format (keynote / talk / …)  | meta   | `format`            |
| Python skill                 | meta   | `python_skill`      |
| Domain expertise             | meta   | `domain_expertise`  |

Mark indexable content with `data-pagefind-body`. Mark non-indexable
shell (header, footer, sidebar) excluded automatically because they're
outside the body element.

### Result presentation

- A `/search/` page with the default Pagefind UI, scoped to the
  conference.
- A keyboard shortcut (`/`) opens a modal from any page.
- Result cards show: page type icon, title, breadcrumb, two-line
  excerpt with highlights.

### Schema.org SearchAction

Add to the site-level WebSite JSON-LD:

```json
"potentialAction": {
  "@type": "SearchAction",
  "target": "https://2026.pycon.de/search/?q={search_term_string}",
  "query-input": "required name=search_term_string"
}
```

So Google can offer in-SERP search for the site.

---

## 5. Privacy & legal

- Pagefind runs entirely client-side — no analytics, no third-party
  requests. Index is served from the same origin.
- Transcripts are auto-generated; the existing diarization note already
  warns that speaker labels reflect diarization, not identity.
- Speaker pages already show consent-derived bio and socials.

No additional consent flow required.

---

## 6. Rollout order

1. **Pagefind on existing content** (this PR) — covers talks + speakers + transcripts; ships with a `/search/` page.
2. **Breadcrumbs everywhere** — small template + macro, BreadcrumbList JSON-LD.
3. **Track index pages** — `/tracks/` + `/tracks/{slug}/` + archive equivalents.
4. **Related-talks block on every talk page** — same speaker, same track, same edition.
5. **Other-editions block on speaker pages** — cross-year speaker continuity.
6. **Sitemap index** — segmented per content type.
7. **SearchAction JSON-LD** — depends on /search/.

Each step is independently shippable. No step depends on a database
migration or backend service.

---

## 7. Open questions

- Tag taxonomy: `talk.tags` is currently a free-text field. Do we want
  curated tags (controlled vocabulary) or accept the long-tail of
  raw-Pretalx values? Recommendation: surface raw tags only on talk
  pages; do not generate tag index pages until a curated set exists.
- Track slug source: derive from `track` label with a slugify (Python
  `python-slugify`), or maintain a manual mapping in `databags/tracks.yaml`?
  Recommendation: start with derived slugs; promote to mapping if track
  labels change between editions and we want a single canonical URL.
- Cross-edition speaker identity: speakers are stored by Pretalx code,
  but codes change between editions. We may need a manual
  `databags/speaker_aliases.yaml` to link the same person across years.
  Out of scope for this PR.
