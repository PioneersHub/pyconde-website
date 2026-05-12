# Development

Lektor-based static site. Python 3.12+, `uv` recommended.

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

For the contact-form backend extras:

```bash
uv pip install -e ".[backend]"
```

Devcontainer alternative: open the repo in VS Code with the Dev Containers extension installed. The container ships with everything the project needs.

## Run

```bash
make run             # Lektor dev server on :5001 (reloads on save)
make build           # Full production build into site/
```

Caveat: the dev server (`make run`) does **not** run the post-build steps — track generation, redirect HTML pages, and the Pagefind index. When iterating on those, run `make build` and serve `site/` directly (see [docs/search.md](search.md) for the launch profile).

## Build phases

```text
make redirects     # databags/redirects.yaml → content/<old-path>/contents.lr + site-config/*.conf
make tracks        # scan talks → content/tracks/, content/archive/{year}/tracks/
make lektor-build  # Lektor → site/
make pagefind      # site/ → site/pagefind/
```

`make build` runs the four in order. Run individual phases when iterating on their inputs.

## Project structure

```text
content/           Page content + structure (Lektor .lr files)
models/            Content-type definitions (Lektor .ini)
templates/         Jinja2 templates
templates/macros/  Reusable template components — see docs/components.md
databags/          YAML / JSON config (single source of truth for everything configurable)
assets/            Static files (CSS, JS, images)
flowblocks/        Reusable content blocks
packages/          Custom Lektor plugins (yaml-databags)
utils/             Python scripts: importers, generators, sync
backend/           FastAPI contact-form service (separate deploy)
docs/              This documentation
```

## Custom Jinja filters

Defined in `packages/yaml-databags/lektor_yaml_databags.py` and registered on the Lektor environment:

| Filter | Purpose |
|---|---|
| `shift_headings` | Demote `<h1>..<h5>` in a markdown body by one level so author headings don't collide with the template `<h1>` |
| `markdown_inline` | Render `**bold**` to `<strong>` in plain strings (forms, single-line fields) |
| `paragraphize` | Split a YAML scalar into `<p>` blocks |
| `social_url` | Normalise social-media handles / URLs to a canonical full URL — see [docs/seo.md](seo.md) |
| `social_label` | Short display form of a social URL |

The same plugin also patches Lektor's databag loader to recognise `.yaml` / `.yml` alongside the built-in `.json` / `.ini`.

## Common follow-ups

| Task | Doc |
|---|---|
| Add a new template component | [docs/components.md](components.md) |
| Add a new subsite | [docs/subsites.md](subsites.md) |
| Add a new redirect | [docs/redirects.md](redirects.md) |
| Pretalx import | [docs/pretalx.md](pretalx.md) |
| Deploy | [docs/deployment.md](deployment.md) |
