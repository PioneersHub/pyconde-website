# Adding a subsite

A subsite is a top-level section under the current edition (e.g. `/masterclasses/`, `/financial-aid/`, `/team/`) that isn't a blog post, talk, or speaker. New subsites touch four layers in lockstep.

## Layers

| Layer | What | Reference |
|---|---|---|
| Model | Field schema in `models/{name}.ini`. Declares which fields the subsite's `contents.lr` accepts. | See `models/financial-aid.ini` |
| Databag (optional) | YAML / JSON in `databags/` if the subsite renders structured content (e.g. a list of grants, FAQ items). Skip this layer if the page is essentially static markdown. | See `databags/faqs.yaml` |
| Content | `content/{name}/contents.lr` carrying `_model: {name}` plus the field values, and any child folders for nested pages. | |
| Template | `templates/{name}.html` extending `layout.html`. Uses the macros library for shared components — breadcrumbs, hero, carousel, etc. | See [docs/components.md](components.md) |

## Walk-through

The faqs subsite is a representative example:

1. **Model** — `models/faqs.ini` declares the fields the page accepts (title, intro, body). A `faq-item` child model declares the per-item schema.
2. **Databag** — `databags/faqs.yaml` holds the structured Q&A; the template iterates this rather than the content tree, so reordering items is a YAML edit.
3. **Content** — `content/faqs/contents.lr` (`_model: faqs`) is essentially a stub pointing at the databag.
4. **Template** — `templates/faqs.html` renders the page, including `FAQPage` JSON-LD for SEO.

Use this pattern when the content is structured and re-orderable. For mostly-static text use the simpler `standard-page` model: a single `contents.lr` with title + body markdown, no databag.

## Linking the subsite

Add an entry to `databags/links.yaml` so the page appears in the navigation:

```yaml
pages:
  - name: My Subsite
    path: /my-subsite/
    topnav: true        # show in the persistent desktop top nav
```

`topnav: false` keeps the page in the hamburger sidebar and footer but off the top bar. Use `topnav: true` sparingly — the top nav is width-constrained and currently fits eight items at 1024 px.

## Conventions

- Render the page inside a `<section class="subsite">` wrapper so it picks up the standard padding and max-width.
- Include the breadcrumb at the top of `{% block body %}` via the macro in `templates/macros/breadcrumbs.html` — see existing subsite templates for the call pattern.
- If the page is publicly indexable, emit `BreadcrumbList` JSON-LD inside `{% block structured_data %}` (the `breadcrumb_jsonld` macro handles this).
- If the page should be excluded from search engines, add its path to `noindex_paths` in `databags/seo.yaml`.
- Mark interactive widgets, dynamic blocks, or sidebar-style navigation with `data-pagefind-ignore` so they don't pollute search excerpts. See [docs/search.md](search.md).
