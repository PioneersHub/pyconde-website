# Reusable Template Components

All reusable UI components live in `templates/macros/` as Jinja2 macros. Import them with `{% from "macros/<file>" import <macro> %}` and call in any template.

Components that render homepage sections are **data-driven** — content comes from YAML databags in `databags/`, so adding or reordering items requires no template changes.

---

## Carousel — `macros/carousel.html`

Multi-instance carousel with two display modes. Renders slides from a databag with navigation controls, keyboard support, touch/swipe, auto-advance, and random slide order.

**Modes:**

- `multi` — 3 cards on desktop, 1 on mobile, sliding transition
- `spotlight` — 1 slide at a time, crossfade transition

**Usage:**

```jinja2
{% from "macros/carousel.html" import render_carousel %}
{{ render_carousel(
    bag('featured')['featured_items'],
    carousel_id='featured',
    mode='multi',
    image_dir='featured',
    section_label='Featured speakers and sessions'
) }}
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `items` | *(required)* | List of item dicts from a databag |
| `carousel_id` | `'carousel'` | Unique ID for this instance (scopes DOM IDs) |
| `mode` | `'multi'` | `'multi'` or `'spotlight'` |
| `image_dir` | `'featured'` | Subdirectory under `/static/media/` for images |
| `section_label` | `'Carousel'` | Accessible `aria-label` for the section |
| `header_title` | `''` | Optional heading above the slides |
| `header_teaser` | `''` | Optional teaser line below the heading |

**Item schema** (all databags use the same format):

```yaml
- id: unique-slug
  type: keynote          # drives badge color
  name: "Speaker Name"
  title: "Talk Title"
  teaser: "1-2 sentence hook"
  image: speaker.jpg     # filename in /static/media/<image_dir>/
  image_alt: "Description"
  link_text: "Learn more"
  link_url: /target-page
```

**Databags using this component:** `featured.yaml`, `masterclasses.yaml`

**Behavior** (provided by `static/js/carousel.js`): auto-advance every 5 seconds, pause on hover/focus, keyboard arrows, touch swipe, random slide order on page load. Multiple carousel instances on the same page operate independently.

---

## Image Reel — `macros/image-reel.html`

Horizontally scrollable strip of conference photos with lazy loading.

**Usage:**

```jinja2
{% from "macros/image-reel.html" import render_image_reel %}
{{ render_image_reel(
    bag('promo_pics')['promo_images'],
    section_label='Conference photos'
) }}
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `images` | *(required)* | List of image paths from a databag |
| `section_label` | `'Conference photos'` | Accessible `aria-label` for the section |
| `alt_text` | `'Conference photo'` | Alt text applied to every image |

**Databag schema** (`promo_pics.yaml`):

```yaml
promo_images:
  - /static/landing-page/promo_images/photo1.jpg
  - /static/landing-page/promo_images/photo2.jpg
```

**Image guidelines:** Landscape format, minimum 800px wide, JPEG recommended. Place files in `assets/static/landing-page/promo_images/`. Images render at min-width 400px.

---

## Sponsors List — `macros/sponsor.html`

Renders sponsor logos grouped by tier (Keystone, Platinum, Gold, etc.). Each logo links to the sponsor's detail page.

**Usage:**

```jinja2
{% from "macros/sponsor.html" import render_sponsors_list %}
{{ render_sponsors_list() }}
```

**Parameters:** None — reads directly from `bag('sponsors')['types']`.

**Databag:** `sponsors.yaml`. Each sponsor type has an `id`, `name`, and list of `sponsors` with `id`, `name`, `logo`, and optional `scale`.

**Adding a sponsor:** See `docs/sponsors_partners.md`.

---

## Blog Post — `macros/blog.html`

Renders a single blog post with title, author, date, and body content.

**Usage:**

```jinja2
{% from "macros/blog.html" import render_blog_post %}
{{ render_blog_post(post) }}
{{ render_blog_post(post, from_index=true) }}
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `post` | *(required)* | Lektor record with `title`, `author`, `twitter_handle`, `pub_date`, `body` |
| `from_index` | `false` | When `true`, title becomes a link to the full post |

---

## Pagination — `macros/pagination.html`

Previous/next navigation for paginated content (blog index, etc.).

**Usage:**

```jinja2
{% from "macros/pagination.html" import render_pagination %}
{{ render_pagination(pagination) }}
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pagination` | *(required)* | Lektor pagination object with `has_prev`, `has_next`, `prev`, `next`, `page` |

---

## Team Member — `macros/team.html`

Three helper macros for rendering team member profiles.

**Usage:**

```jinja2
{% from "macros/team.html" import render_team_member_image, render_team_member_role, render_team_member_socials %}

{{ render_team_member_image(member.image) }}
{{ render_team_member_role(member.role, member.type) }}
{{ render_team_member_socials(member) }}
```

**Macros:**

| Macro | Parameters | Description |
|-------|------------|-------------|
| `render_team_member_image(image_file)` | Filename or empty | Shows member photo or default placeholder |
| `render_team_member_role(role, type)` | Role string, optional type | Displays role with optional type prefix |
| `render_team_member_socials(member)` | Member dict | Renders icons for website, LinkedIn, GitHub, Bluesky, Mastodon, Twitter |

**Databag:** `team.yaml` (provides `team_images` base path and `default_image`).
