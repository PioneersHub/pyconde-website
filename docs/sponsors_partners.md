# Sponsors and community partners

Two entities share the same data shape and pipeline:

- **Sponsors** — paid tiers (Keystone, Strategic, Tier-1, …). Source: `databags/sponsors.yaml`.
- **Community partners** — non-commercial supporters. Same YAML; partners typically live under a dedicated `type` block at the bottom of the file.

Sponsor pages, the homepage sponsor strip, and the dedicated `/sponsors/` directory are all generated from this single YAML file.

## YAML shape

```yaml
types:
  - name: Keystone                       # tier display label
    id: keystone                         # slug used in templates and URLs
    sponsors:
      - name: Merck
        id: merck                        # slug; matches the logo filename and content folder
        headline: ''
        description: |
          Merck is a leading science and technology company …
        website: https://www.merckgroup.com/en
        logo: /static/media/sponsors/merck.svg
      - name: …
```

`description` accepts HTML (rendered as-is — escape carefully); use it for paragraph breaks and links.

## Add a sponsor

1. Drop the logo at `assets/static/media/sponsors/{id}.svg`. Prefer SVG; PNG works as a fallback for raster-only artwork.
2. Add the sponsor entry under the right `type` block in `databags/sponsors.yaml`. Keep entries sorted within a tier — match the order you want them to appear on the page.
3. Generate the per-sponsor content pages:

   ```bash
   make sponsor-pages
   ```

   New entries are added to `content/sponsors/{id}/contents.lr`. The target adds the new files to git via `git ls-files --others`; review the diff and commit.
4. `make build` picks up the new content on the next build.

The thank-you copy for sponsors who funded specific things (financial aid, PyLadies tickets, etc.) lives in `databags/sponsoring_cta.yaml`. Update it independently of the sponsor list.

## Add a community partner

Same flow, different type block. Community partners typically don't have a tier hierarchy — keep them in a single `type` (e.g. `community`). The template renders them with the same card layout as sponsors but on a separate strip.

## Common follow-ups

| Symptom | Fix |
|---|---|
| Sponsor page is 404 after build | `make sponsor-pages` was not run, or the new `content/sponsors/{id}/contents.lr` is not committed |
| Logo shows broken | Logo filename does not match `id` in the YAML, or the file isn't in `assets/static/media/sponsors/` |
| Sponsor in the wrong tier | Move the entry to the right `type` block in the YAML; re-run `make sponsor-pages` |
| Description rendering as escaped HTML | Use `|` for multi-line YAML scalars to preserve markup; the template trusts the field |
