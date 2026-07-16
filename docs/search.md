# Site search

Full-text search across the current edition plus every archived edition, served entirely client-side from a static Pagefind index. No server, no third-party analytics.

## What gets indexed

`make build` invokes Pagefind after Lektor finishes. Pagefind walks `site/` and indexes every page that:

- Has a top-level `<html>` element (the lone exception is the Google verification file, which has no `<html>` tag — Pagefind warns and skips it).
- Does **not** carry `<meta name="robots" content="noindex">` (so redirect pages are skipped automatically).

Inside each indexable page, only content within an element marked `data-pagefind-body` is searched. The current markers:

| Template | Body element | Notes |
|---|---|---|
| `talk.html` | `<article class="talk-article" data-pagefind-body>` | Title, abstract, full description, speakers, full transcript |
| `speaker.html` | `<article class="speaker-article" data-pagefind-body>` | Name, bio, company, talks list |

Other pages (blog posts, sponsor pages, FAQs, static pages) are indexed via Pagefind's default `<main>` fallback.

Filter facets are declared on the same articles using hidden `<span data-pagefind-filter="key:value" hidden></span>` elements (one element per filter — HTML parsers collapse duplicate attributes on the same tag, so they have to be separate elements).

Talks declare: `year`, `kind=Talk`, `format` (talk / keynote), `track`, `recording` (yes / no), `transcript` (yes / no), `python_skill`, `domain_expertise`.

Speakers declare: `year`, `kind=Speaker`.

## /search/ page

Single page at `/search/` hosts the Pagefind UI bundle, scoped to the conference and pre-styled to match the site palette.

Features:

- URL `?q=` prefill so external links can deep-link a query (and so the `SearchAction` JSON-LD on the homepage works for Google's in-SERP search box).
- `/` keyboard shortcut to focus the input from any page.
- Filter sidebar shows the eight facets above with auto-generated value lists. A small post-render JS pass swaps underscored filter names (`python_skill`) for spaces (`Python skill`).
- Search-action JSON-LD on the page declares the entry point at `/search/?q={search_term_string}` per Google's spec.

## Local development

The Lektor dev server **does not serve the Pagefind index** — it doesn't know about the `pagefind/` directory and prunes it on the next reload. For search-testing locally, use the static profile:

```bash
make build
python3 -m http.server 8088 --directory site
```

Or, with the bundled launch profile:

```text
.claude/launch.json → "static" profile → port 8088
```

Pagefind itself is a `make build` step:

```bash
make pagefind        # site/ → site/pagefind/   (~12 MB, ~10 KB shards loaded on demand)
```

## Updating the indexer

`pagefind` (Python wrapper) + `pagefind_bin` (bundled native binary) are pinned as dev dependencies in `pyproject.toml`. Bump together:

```bash
uv add --dev "pagefind>=1.5.2"
uv add --dev "pagefind_bin>=1.5.2"
```

The CSS / UI bundle ships with the same package, so a major version bump may require revisiting the override CSS in `templates/search.html` (`--pagefind-ui-*` variables).

## Common follow-ups

| Symptom | Fix |
|---|---|
| New filter facet doesn't show up | Add a `<span data-pagefind-filter="key:value" hidden></span>` inside the `data-pagefind-body` article in the relevant template, rebuild |
| Talk indexed but transcript missing from search | Verify the transcript is rendered in the same `data-pagefind-body` article (it is, in `talk.html`) and that the talk's `transcript_status != 'none'` |
| Pagefind warns "page has no `<html>` element" | Acceptable for verification files (Google site-verification HTML) — the page is intentionally bare and not search-relevant |
| Search returns no results in `make run` | Expected; the Lektor dev server doesn't expose `pagefind/`. Use the static profile above |
