# SEO machinery

How crawlers, in-SERP features, and the Knowledge Graph see the site. All machinery is template-resident; nothing requires a server-side change.

## What every page emits

`templates/layout.html` is the single point of truth for the head block. Every page inherits:

- `<title>` + `<meta name="description">`, populated per-page or via `databags/branding.yaml` defaults.
- `<link rel="canonical">` to the absolute URL.
- `<meta name="robots" content="noindex, nofollow">` for paths listed in `databags/seo.yaml` (`noindex_paths`).
- Open Graph + Twitter card meta (image is `social_card_image` or the site default).
- Site-wide `WebSite` + `Organization` JSON-LD (single `@id` per host so other schemas can reference them).
- Theme color, favicons, manifest.
- Google + Bing crawler hints, plus AI-crawler allowlist via `databags/seo.yaml`.

The `<main id="main-content">` wrapper is what Pagefind treats as the indexable body when a template doesn't declare its own `data-pagefind-body`.

## Page-type schema

| Page kind | Schema | Notes |
|---|---|---|
| Talk | `Event` (`EventScheduled` / `EventCompleted` based on whether under `/archive/`) | `recordedIn` → VideoObject; `subjectOf` → `#transcript` fragment if transcript present; `superEvent` → edition's `Event @id` |
| Recording | `VideoObject` | Includes `transcript:` URL, `inLanguage` from `transcript_language`, `isPartOf` → talk `Event` |
| Speaker | `Person` | `sameAs[]` lists canonical social URLs (see [Social link normalisation](#social-link-normalisation)); `performerIn[]` references each talk `Event @id` |
| Edition (`/archive/{year}/`) | `Event` (EventCompleted) | Stable `@id` so per-edition talks can `superEvent`-reference it |
| Track | `CollectionPage` | `hasPart[]` lists every talk `Event @id` in the track |
| Speaker list | `ItemList` | Talk lists rely on the per-page `Event` schema, no list-level wrapper |
| `/search/` | `WebSite.potentialAction: SearchAction` | Powers Google's Sitelinks Search Box; template at `templates/search.html` |

`BreadcrumbList` JSON-LD is emitted on every detail / index page via the macro in `templates/macros/breadcrumbs.html`. The visible breadcrumb above the page content uses the same trail.

## Sitemaps

`/sitemap.xml` is a **sitemap index** referencing seven segments. Each segment lists URLs of one content kind so indexing problems are easy to spot in Search Console and no segment risks the 50k-URL limit.

```text
/sitemap.xml                     (sitemap index)
/sitemaps/pages.xml              ~100  static and CMS pages
/sitemaps/talks-current.xml      ~150  current edition's talk pages
/sitemaps/talks-archive.xml      ~700  every archived talk
/sitemaps/speakers-current.xml   ~165
/sitemaps/speakers-archive.xml   ~775
/sitemaps/tracks.xml             ~110
/sitemaps/blog.xml               ~22
```

Filtering logic lives in `templates/sitemap-segment.xml`; the segment name is derived from each page's URL path (`/sitemaps/{name}.xml`). Per-URL `<image:image>` and `<video:video>` entries are emitted by the shared `templates/macros/sitemap-url.html` macro.

To add a new segment: create `content/sitemaps/{name}.xml/contents.lr` with `_template: sitemap-segment.xml` and `_model: none`, then extend the filter block in `sitemap-segment.xml` and reference the new file from `templates/sitemap.xml`.

## Social link normalisation

Speaker contents.lr files carry social fields imported across years with mixed shapes — bare handles (`hendorf`), at-prefixed handles (`@hendorf`), full URLs (`https://twitter.com/hendorf`), mastodon webfinger ids (`@user@server.tld`), path-style entries (`server.tld/@user`).

Two Jinja filters live in `packages/yaml-databags/lektor_yaml_databags.py`:

| Filter | Purpose |
|---|---|
| `social_url(value, kind)` | Normalises any recognised shape to a canonical full URL. `kind` ∈ `twitter`, `x`, `mastodon`, `bluesky`, `threads`, `github`, `linkedin`, `homepage`. Returns `''` for blanks, placeholders (`-`, `n/a`), or unparseable strings. |
| `social_label(value, kind)` | Short display label (e.g. `@hendorf`, `@user@server.tld`, `cheuk.dev`) stripped of scheme and `www.`. |

Both are used in `speaker.html` for the JSON-LD `sameAs[]` array and the visible `<ul class="speaker-socials">` so search engines and users always see the same canonical URL. Source `contents.lr` data stays raw — the next Pretalx re-import diff is not polluted by render-time fixes.

## Crawler config

| File | What |
|---|---|
| `databags/seo.yaml` | `noindex_paths`, `disallow_paths`, AI-crawler allowlist (`GPTBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`, `CCBot`) |
| `content/robots.txt/contents.lr` + `templates/robots.txt` | Renders `robots.txt` from the YAML above |
| `content/llms.txt/contents.lr` + `templates/llms.txt` + `llms-full.txt` | LLM-crawler discovery files (linked from the homepage) |

## Cross-linking concept

The end-to-end SEO + UX plan that drove most of the above is documented in [seo-crosslinking-concept.md](seo-crosslinking-concept.md). That file is the design rationale; this one is the operator's reference.
