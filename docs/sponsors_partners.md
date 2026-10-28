# Sponsors and community partners

Sponsors and partners share one data file and one pipeline:

- **Sponsors**: paid tiers (Keystone, Platinum, Gold, Silver, Community Sponsors).
- **Institutional sponsors and partners**: non-commercial supporters (Institutional Sponsors, Diversity Sponsors, Community Partners, Technical Partners).

The current edition lives in `databags/sponsors.yaml`. It feeds the sponsor wall on the front page and on `/sponsors/` (both through `render_sponsors_list` in `templates/macros/sponsor.html`) and the per-sponsor pages under `/sponsors/{id}/`.

Past lineups are frozen in `databags/sponsors_{year}.yaml` (for example `sponsors_2026.yaml`). Do not edit them; copy an entry into `sponsors.yaml` when a past sponsor is confirmed again.

## YAML shape

```yaml
types:
  - name: Platinum                       # tier name, used in the sponsor page subtitle
    id: platinum                         # slug; also referenced by past_editions.tier_order
    logo_size: lg                        # xl | lg | md | sm — logo box size on the wall
    sponsors:
      - name: QuantCo
        id: quantco                      # slug; becomes /sponsors/{id}/
        headline: QuantCo
        description: |
          QuantCo is an Applied AI company. …<br/><br/>
          …
        website: https://www.quantco.com
        logo: /static/media/sponsors/Q_quantco_BLACK.svg
        scale: null                      # optional optical correction: scale-90 | scale-80 | scale-70 | scale-60
  - name: Community Partners
    id: community-partners
    group: Partners                      # divider label instead of logo_size
    sponsors: []
```

`description` accepts HTML (rendered as-is — escape carefully); use it for paragraph breaks and links.

### How a tier renders

Each tier sets exactly one of:

- `logo_size` — the tier gets its own centred logo row, sized `xl`, `lg`, `md` or `sm`. The tier name is not shown; size carries the tier.
- `group` — a divider label. All tiers with the same label are collected into one row of small logos under that label, in order of first appearance (for example Diversity Sponsors, Community Partners and Technical Partners all sit under "Partners").

Tiers without sponsors are skipped, so empty tiers can stay in the file.

Every logo is contained in a box with a fixed width and height for its tier. Use `scale` only when a logo still looks too heavy next to its neighbours; leave it `null` otherwise.

### Past sponsors strip

`past_editions` in `sponsors.yaml` drives the moving line of past sponsors below the current wall:

| Key | Purpose |
| --- | --- |
| `title` | Divider label above the strip |
| `bags` | Frozen lineups to read, newest first |
| `featured` | Ids shown first, in this order — picked by how widely the name is known, not by tier |
| `tier_order` | Ranking of every tier id used in the past lineups; the rest of the strip is ordered by best tier held, then number of editions, then most recent edition |
| `tonal_logos` | Ids whose logo is a filled shape with knocked-out text; these render in greyscale instead of a dark silhouette |

A sponsor shows once, and anyone in the current lineup is left out of the strip.

## Add a sponsor

1. Drop the logo at `assets/static/media/sponsors/`. Prefer SVG; PNG works as a fallback for raster-only artwork.
2. Add the sponsor entry under the right tier in `databags/sponsors.yaml`. Within a tier, logos appear in file order.
3. Generate the per-sponsor content pages:

   ```bash
   make sponsor-pages
   ```

   This validates `sponsors.yaml` (unique ids, tier layout, `past_editions` references) and writes `content/sponsors/{id}/contents.lr` for every current sponsor. New files are added to git; review the diff and commit.
4. `make build` picks up the new content on the next build.

### Share images

A sponsor page uses `content/sponsors/{id}/social_card.png` as its share image when that file exists.
Without it, the page shares the edition's site card (`social_card` in `PyconDE.lektorproject`).
After adding a card, re-run `make sponsor-pages` so the page points at it.

There is no 2027 thank-you card template yet; the banners in `assets/static/media/thank_you_banners/` are from past editions and must not be copied in.

The sponsoring call to action shown on the front page and at the bottom of `/sponsors/` lives in `databags/frontpage/sections/sponsoring.yaml`. Its `display` flag switches it off in both places.

## Common follow-ups

| Symptom | Fix |
| --- | --- |
| Sponsor page is 404 after build | `make sponsor-pages` was not run, or the new `content/sponsors/{id}/contents.lr` is not committed |
| Logo shows broken | The `logo` path does not match a file in `assets/static/media/sponsors/` |
| Sponsor in the wrong tier | Move the entry to the right tier in the YAML; re-run `make sponsor-pages` |
| Description edit not visible on the sponsor page | The page copy is generated: edit `sponsors.yaml`, then re-run `make sponsor-pages` |
| `make sponsor-pages` fails with "Invalid sponsor wall configuration" | A tier has both or neither of `logo_size`/`group`, or a `past_editions` id or tier is not in the past lineups |
| Sponsor's own share card not used | Re-run `make sponsor-pages` after adding `content/sponsors/{id}/social_card.png` |
| Description rendering as escaped HTML | Use a `\|` block scalar to preserve markup; the template trusts the field |
