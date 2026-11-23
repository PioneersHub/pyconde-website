# Social Cards 2027 — Brand Audit and Engine Plan

> Status: **implemented and locally verified** (2026-10-27). Decisions taken at approval: HarfBuzz/fontTools/resvg
> rendering stack, exports og + square + portrait + story, unaltered square-cornered photo panels (provisional),
> deterministic critique only. Usage and the verified/provisional rule list live in `docs/social_cards.md`.
>
> Deviations from the plan below: Field also carries speakers (keynotes); strategies are restricted per field
> (`strategy_fields`, spine only on white/ink, python only on blue); a card's photo must appear on it; photos enlarged
> more than 1.5× are rejected; the CTA turns ink on a yellow field (§06 default button).
>
> **Amended 2026-11-23.** Site pages get cards too (`make page-cards`, recipes in `utils/social_cards/pages.yaml`), with one fixed visual
> family per content type (talk, keynote, masterclass, news, page). Generated PNGs carry a record of their content and a pixel checksum:
> cards are redrawn only when that content or `brand.yaml` changes, and any other PNG is hand-made and never replaced.
>
> **Amended again 2026-11-23.** Backgrounds are no longer fixed per category or strategy (`strategy_fields` is gone). Every card takes one of
> blue, green, orange or yellow (`backgrounds`), picked from a hash of its id: random across cards, stable for each card. Content types
> are told apart by layout instead: spine for talks, python for blog posts, corner monogram for masterclasses, large monogram for pages.
>
> Same day, sponsors: the generated sponsor cards were removed. Sponsors get thank-you cards instead (`thanks` strategy): tier, "Thank you
> for your support!" and the sponsor's logo on the sponsor-section off-white. They stay `preview_only` until confirmed in `make card-preview`,
> a local gallery of every card on every background and format with scores and rejection reasons.

## 1. What exists today

| Piece | Where | State |
| --- | --- | --- |
| Talk-card generator | `utils/social_card_img_gen.py` | Draws onto 7 pre-made PNG templates with Pillow, wraps by character count (`MAX_CHARS_PER_LINE = 55`), random colour, no fit check, no shaping (Pillow built without raqm) |
| Talk-card templates | `assets/static/media/social/social-card-templates/` | **2026 identity** — "PyConDE PyData Darmstadt 14–17 April '26" lockup. Obsolete for 2027 |
| 318 rendered talk cards | `assets/static/media/social/talks/` | 2026 talks, referenced by archive pages. Leave untouched |
| Site default card | `assets/static/media/social_card.png` (3402×1786) | **The only verified 2027 card** (commit `8508cb85`, 2026-08-04): silver field, white 2027 monogram, vertical python bars |
| OG contract | `templates/layout.html:61-87` | `og:image` 1200×630 PNG, per-page `social_card_image` field on 9 models |
| Design guide | `design_guidelines/` | **2026 edition** (its own `naming.note` says so). Colour table and forbidden pairs still match the 2027 palette; logo rules do not |

## 2. Verified 2027 brand rules

Sources: live <https://pycon.de/> (computed styles, 2026-10-27), `assets/static/css/main.css` / `custom.css` (comments cite "Design Rules §00–§11"), `assets/static/logo-2027/*.svg`, `databags/branding.yaml`.

### Mandatory

- **Name**: "PyCon DE 2027". Never "PyCon DE & PyData 2027", never "PyConDE PyData".
- **Event facts** come from `databags/branding.yaml` only: 20–22 April 2027, HCC Heidelberg; Masterclasses 19 April; Sprints 23–24 April.
- **Palette** (`main.css :root`, matches logo SVG fills):
  orange `#ff9b00`, yellow `#fac800`, lime `#96dc00`, cyan `#00c8e1`, blue `#3778be`, green `#00aa41`, silver `#b7bcbf`,
  secondary coral `#e54f53`, red `#c41011`, pink `#e199c3`, magenta `#d14190`, light blue `#a2d9ef`, light lime `#d5f199`,
  white `#ffffff`, ink `#111111`.
- **Logo**: the 2027 monogram (P-Y-C-O-N-D-E line letterforms), aspect 868.11 : 1330.70. Nine official colour files:
  orange, yellow, lime, cyan, blue, green, white, silver, black. Used as-is, uniform scale only — no recolouring outside those nine files, no re-drawing.
- **Square corners** everywhere (§11).
- **Flat colour, no gradients** on cards (`custom.css`: "the brand allows no gradients"). See conflict below.
- **§02 text-safe grounds**: running text sits on white, ink, blue, green or orange — never on silver.
  Display type also appears on yellow (blue text, `.why-attend`).
- **Field/text pairs used on the live site**: blue → white, green → white, orange → ink, yellow → blue, white → ink, ink → white.
- **Seven-colour brand bar** (§05): fixed order yellow · cyan · blue · green · orange · lime · silver.
- **Accent spine** (§06): a slim solid colour bar on the left of a card/item.
- **CTA** (§06): yellow fill, ink text, 2 px ink border, uppercase, 700, letter-spacing 0.08em.

### Typography (verified on the live site)

- Family actually rendered: **IBM Plex Sans** 400/500/600/700 (the repo ships these TTFs).
  CSS lists "Helvetica Neue" first in a few legacy rules; the 2026 guide names Helvetica Neue. Cards will use IBM Plex Sans — what the 2027 site renders and what is licensed to ship.
- Display headline: 700, line-height 1.02, tracking −0.02em (`.intro__headline`).
- Section titles: 700, tracking −0.02em.
- Labels / CTAs: 700, uppercase, tracking 0.08em.
- No italics.

### Allowed variation

- Field colour from the primary palette, following the pair table above.
- Logo colour from the nine official files, chosen for contrast with the field.
- Python illustrations `assets/static/pythons/Python_01–56.png` (body colours yellow, cyan, green, lime, orange, silver — no blue, so they are drawn for the blue field;
  the blog fallback uses `Python_50` on blue, §05). On any other field, a python is only allowed when none of its body colours equals the field.
- Brand bar, accent spine, CTA plate.

### Unresolved — will not guess

1. **Logo clear space for 2027.** The 2026 rule ("X on all sides", X = one wordmark line) does not map onto the new monogram. Proposed working rule: clear space ≥ ¼ of logo width; flagged in the spec as provisional.
2. **Photo treatment.** 2026 had pixel-art portraits; the 2027 hero uses a blue gradient scrim over photos, which contradicts the no-gradient rule. No 2027 card shows a photo.
3. **Gradient conflict.** Hero scrim (`main.css` "Brand-hued scrim") vs. "the brand allows no gradients". Cards will stay flat.
4. **Forbidden colour pairs** in `design_guidelines/design-system.json` are from the 2026 guide. Same palette, so I will enforce them, marked "inherited from 2026".
5. **Secondary colours** (coral, magenta, …) appear in the default card's python bars, but no 2027 rule says where else they may go. Cards will use them only inside official artwork, never as fields or text.

## 3. Architecture

New package `utils/social_cards/`, replacing the internals of `utils/social_card_img_gen.py` while keeping its entry point, output path (`static/media/social/talks/{code}.png`) and JSON change-cache behaviour.

```text
utils/social_cards/
  brand.yaml        single source of truth: palette, pairs, type scale, grid, logo files, rules
  brand.py          loads brand.yaml + databags/branding.yaml (dates/venue/name), exposes typed spec
  fonts.py          HarfBuzz shaping + fontTools outlines → exact advances, bboxes, side bearings
  typeset.py        line-breaking and size search (see §4)
  content.py        card content model + analysis (category, lengths, speakers, image, language)
  layouts/          composition strategies (see §5), each yields parametrised candidates
  render.py         candidate → SVG (text as glyph outlines, logo SVG embedded) → PNG via resvg
  validate.py       hard brand + geometry checks; any failure rejects the candidate
  critique.py       weighted quality score (35/25/20/10/10) from geometry and rendered pixels
  pipeline.py       analyse → generate → render → validate → score → refine → select → export
  cli.py            `uv run python -m social_cards render cards.yaml` / `talks`
```

**Rendering stack** (new dependencies): `uharfbuzz` (shaping, kerning, ligatures), `fontTools` (glyph outlines, metrics),
`resvg-py` (SVG → PNG, also renders the logo SVGs). Text is converted to outlines before rasterising, so a missing or substituted font is impossible by construction, and the output is byte-deterministic for a given input.

## 4. Typography engine

- Measures every candidate line with real shaped advances; optical left alignment from the first glyph's left side bearing (so "T", "W", "A" sit flush with the grid, not the advance box).
- Line breaking by dynamic programming over all word-boundary break sets (titles are short, so this is exhaustive, not greedy). Cost terms:
  raggedness against the measure; short final line (< 40 % of the longest → heavy penalty, single word → reject);
  break after article/preposition/conjunction (EN + DE lists in `brand.yaml`); bonus for breaking after ":" " – " ","; never split tokens such as `scikit-learn`, `Python 3.14`, `C++`, names.
- Size search over the brand type scale (discrete steps, not continuous shrink). For each size it tries every permitted measure width and line count first; size only drops when no arrangement at the current size scores acceptably.
- Leading and tracking from the spec (display 1.02 / −0.02em, labels 0.08em caps), adjusted for size; baseline grid shared by all text blocks.
- Hierarchy ratios enforced: headline ≥ 1.8× speaker line ≥ 1.25× metadata; minimum rendered sizes per export format.

## 5. Layout strategies

Each is built on a shared grid (margins, columns and baseline derived from the canvas short side), and each yields several candidates (headline measure, alignment block position, field colour, decoration).

| Strategy | Look | Categories |
| --- | --- | --- |
| **Field** | Full colour field, large headline, logo + facts block, brand bar at the foot | Conference announcement, CfP, tickets, sponsorship, community/volunteer calls |
| **Spine** | White or ink field, headline beside a coloured accent spine, speaker block, small logo | Talk/session cards, editorial/news |
| **Python** | Blue field, one official python as counterweight, headline in the opposite quadrant | News, community, schedule teasers, short headlines |
| **Portrait** | Square-cornered photo panel + colour field text (depends on unresolved photo rule) | Keynote, speaker spotlight, masterclass instructor |
| **Dates** | Key-dates list with per-row colour spines (as on the front page) | Important dates, schedule announcements |

Category profiles (in `brand.yaml`) say which strategies, fields and hierarchy each category may use;
the pipeline picks among compliant candidates per card, and a deterministic seed (card id) keeps a card stable across runs while different cards vary.

## 6. Validation and critique

**Hard brand checks** (reject): colours ⊄ palette; text/field pair not allowed; font not one of the four shipped files; logo not an unmodified official file or non-uniform scale or inside its clear space;
"PyData" or a wrong date/venue in 2027 text; "reduced" in ticket copy (categories are Standard and Personal).

**Hard geometry checks** (reject): any element outside the safe area;
text/element bbox collisions; text below the minimum size for the export; overflow; single-word last line.

**Scored critique** (among valid candidates): typography 35 (rag, break quality, size use), composition 25 (pixel-mass centroid vs. optical centre, margin consistency, negative-space distribution),
hierarchy 20 (size ratios, contrast), colour 10 (WCAG contrast, pair preference),
refinement 10 (decoration density, difference from the card's siblings). The top candidates get a local refinement pass (measure, block position, size step) before selection.
This score catches measurable faults; it is not a substitute for a designer's sign-off, and the docs will say so.

## 7. Exports

1200×630 OG (rendered at 2×, 2400×1260, as today's 2× templates), plus the formats you confirm. PNG, sRGB.

## 8. Validation set and tests

- `tests/social_cards/cards.yaml`: very short and very long headlines, 1–4 speakers,
  technical titles (`asyncio`, `C++`, `scikit-learn`, version numbers), German and English, dates/venue, with and without images, every category, every export size.
- Rendered contact sheet next to `social_card.png` for side-by-side review; I review each sheet visually and iterate before calling it done.
- Unit tests: line breaker (no orphans, no split tokens, DE/EN stopwords), size search, every hard check (each must reject a crafted bad card),
  `brand.yaml` palette equals `main.css :root` (so the two cannot drift), every sample card passes validation, determinism (same input → same bytes).

## 9. Out of scope

Regenerating the 2026 talk cards; changing website CSS; the 2026 design-guide app.
