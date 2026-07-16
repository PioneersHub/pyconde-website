# PyCon DE & PyData Website

[![Fetch submissions](https://github.com/PioneersHub/pyconde-website/actions/workflows/fetch_submissions.yml/badge.svg)](https://github.com/PioneersHub/pyconde-website/actions/workflows/fetch_submissions.yml)
[![Upload website](https://github.com/PioneersHub/pyconde-website/actions/workflows/main.yml/badge.svg)](https://github.com/PioneersHub/pyconde-website/actions/workflows/main.yml)
[![Upload staging website](https://github.com/PioneersHub/pyconde-website/actions/workflows/development.yml/badge.svg)](https://github.com/PioneersHub/pyconde-website/actions/workflows/development.yml)

Static site for the PyCon DE & PyData conference, built with Lektor. Serves the current edition plus an archive of every previous edition with talks, speakers, recordings, transcripts, and full-text search.

> **Speakers:** session and bio data come from Pretalx. Update your information there; the website picks up changes on the next scheduled sync. Direct edits to talk or speaker files in this repo are overwritten by the next import.

## Pick your task

The site has three operating modes. Find yours, follow the link.

- **[Running the current edition](docs/live.md)** — daily ops while the upcoming or in-flight conference is live: blog posts, sponsors, landing pages, Pretalx sync, deploys, contact form.
- **[After the conference](docs/post-conference.md)** — once the event is over: link YouTube recordings, import transcripts, switch the landing page to recap mode, cut the edition over to the archive.
- **[Archive](docs/archive.md)** — how prior editions are stored and served: slug URLs, Pretalx-code redirects, per-track index pages, cross-edition speakers, search.

Cross-cutting topics referenced from every phase:

- [Local development setup](#development-setup) (this file, below)
- [Template components and macros](docs/components.md)
- [SEO machinery — sitemaps, breadcrumbs, JSON-LD, social-link normalisation](docs/seo.md)
- [Site search (Pagefind)](docs/search.md)
- [Redirects — manual entries plus generated nginx / Caddy snippets](docs/redirects.md)
- [Deployment](docs/deployment.md)

---

## Development setup

Requires Python 3.12+, `make`, and either `uv` (preferred) or `pip` with `venv`.

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

Run the build pipeline once to materialise generated content (tracks, redirects, Pagefind index):

```bash
make build
```

For interactive editing, the Lektor dev server reloads on file changes but does **not** run the post-build steps (Pagefind index, redirect generation). When testing search or redirects, run `make build` and serve the `site/` directory with a static HTTP server instead — see [docs/search.md](docs/search.md) for the launch profile.

```bash
make run             # Lektor dev server on :5001
make build           # Full production build into site/
```

The optional `[backend]` extra pulls in dependencies for the contact-form FastAPI service. See [docs/contact_form.md](docs/contact_form.md).

---

## License & Notice

- [MIT License](LICENSE)
- [Notice — Logos & Trademarks Excluded](NOTICE.md)
