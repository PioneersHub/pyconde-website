# Social Cards

Social cards (og:image, feed posts, stories) are designed by an engine in `utils/social_cards/`. It does not fill templates.
For every card it builds many brand-compliant layouts, rejects any that break a brand rule, scores the rest and refines the best few. Then it exports the winner.

The talk cards on every talk page come from the same engine (`make fetch-submissions`).

## Running it

The engine needs the `cards` extra (HarfBuzz, fontTools, resvg):

```bash
make social-cards CARDS=tests/social_cards/cards.yaml OUT=/tmp/cards
```

That writes `{id}-{format}.png` for every card and format, plus `contact-sheet.png`, which shows the results beside the official 2027 default card. Options for the script behind it:

```bash
uv run --extra cards python utils/render_social_cards.py CARDS.yaml --out DIR --formats og,square --only cfp-en --verbose
```

`--verbose` prints the runner-up candidates and the reasons others were rejected.

## Card files

```yaml
cards:
  - id: cfp-en                 # required, unique; also seeds the design choices
    category: cfp              # required, see brand.yaml `categories`
    lang: en                   # required: en | de
    headline: Share what you build with Python and AI   # required
    formats: [og, square, portrait, story]              # required
    subline: The Call for Proposals is open
    cta: Submit a proposal
    kicker: Call for Proposals # default: the category label; omitted when it repeats the headline
    speakers:                  # names or {name, affiliation}
      - name: Jonas Weber
        affiliation: Example GmbH
    image: assets/static/media/hero_images/….jpg   # repo-relative; must be used if given
    image_focus_y: 0.4         # vertical crop focus, default 0.3 (as the site hero)
    dates:                     # rows for the key-dates layout
      - {date: 19 April 2027, label: Masterclasses & DjangoGirls}
```

The text is used exactly as written. The engine chooses line breaks and sizes, but it never shortens, rewords or reorders content. A missing required field or an unknown key is an error.

Event facts are never written into a card file. "PyCon DE 2027", the dates and the venue come from `databags/branding.yaml`.

Formats: `og` (1200×630, exported at 2×, the size `templates/layout.html` announces), `square` (1080²), `portrait` (1080×1350), `story` (1080×1920, with text kept clear of the platform UI).

## How a card is designed

| Step | Module | What happens |
| --- | --- | --- |
| Brand spec | `brand.yaml`, `brand.py` | Palette, approved field/text pairs, type roles, logo files, categories. Event facts come from `branding.yaml` |
| Content | `content.py` | Card model and analysis (speakers, image, dates, CTA) |
| Candidates | `layouts/` | Five strategies (below) × permitted fields × variants |
| Typesetting | `fonts.py`, `typeset.py` | HarfBuzz shaping, exhaustive line-break search, discrete size steps, optical margin alignment |
| Validation | `validate.py` | Hard brand and geometry checks; one violation rejects the candidate |
| Critique | `critique.py` | Typography 35, composition 25, hierarchy 20, colour 10, refinement 10 |
| Refinement | `pipeline.py` | Local search around the best four candidates (size step, measure, logo scale, art share) |
| Export | `render.py` | SVG with text as glyph outlines and the official logo SVG embedded verbatim, rasterised by resvg with system fonts disabled |

The output is deterministic: the same card file renders to the same bytes. Variation between cards comes from a seed derived from the card id, and from a penalty for repeating the previous card's composition.

### Strategies

| Strategy | Source on the website | Used for |
| --- | --- | --- |
| Field | Intro, tickets, sponsoring, newsletter, masterclass sections | Announcements, CfP, tickets, sponsoring, community, keynotes |
| Spine | Session and masterclass cards (§06 accent bar), footer brand bar | Talks, speaker spotlights, news |
| Python | Blog-card fallback: python on blue (§05) | News, announcements, schedule |
| Portrait | — (no 2027 photo rule yet, see below) | Cards that come with a photo |
| Dates | Key-dates band | Important dates |

### Typography

- Line breaks are scored like a typographer would score them. Lines should not end on a weak word ("the", "für", "&"). A short single word or a stub on the last line is penalised.
A sentence-case name ("Data Science") stays on one line. A break after a colon or dash counts as a natural pause.
- Version numbers and counts stay with their word ("PyO3 0.22", "40 TB"). Speaker names never break inside.
- Sizes come in the brand's discrete steps. A smaller step is taken only when no arrangement at the larger one is good enough. Layouts also try narrower measures and full-width variants before giving up size.
- Text aligns on its ink, not its advance box, and opening quotes hang. Gaps are measured baseline to cap height, so spacing looks the same at every size.

## What was verified

`utils/social_cards/brand.yaml` marks every rule with its source.

**Verified on the 2027 site and assets:**

- the palette (`main.css :root`, kept in sync by a test);
- IBM Plex Sans 400–700 as the rendered family;
- display type at 700 / 1.02 / −0.02em, and labels in caps with 0.08em tracking;
- square corners and flat colour;
- the colour of each section field and the text colour it carries;
- the seven-colour brand bar and its order;
- the §06 accent spine and CTA;
- the nine official 2027 logo colour files;
- the python artwork on blue;
- the naming "PyCon DE 2027".

**Inherited from the 2026 guide** (same palette, not re-confirmed): the forbidden text/field colour pairs.

**Provisional, to be replaced when the 2027 design rules define them:**

- *Logo clear space:* ¼ of the logo width. Layouts leave more (`logo_gap`).
- *Photo treatment:* photos are used unaltered, in a square-cornered panel, and never enlarged more than 1.5×.
- *Brand typeface:* the 2026 guide names Helvetica Neue, and some legacy CSS lists it first. The live 2027 site renders IBM Plex Sans, and that is what the cards use.
- *Gradients:* the site hero uses a gradient scrim, while `custom.css` says the brand allows none. Cards stay flat.

## Limits

The critique catches measurable faults (rag, orphans, crowding, scattered negative space, weak hierarchy, low contrast, repetition) and breaks ties between good options.
It is not a designer's sign-off. Review the contact sheet before publishing.

Some checks are beyond it:

- **Photo content:** it cannot see that a photo shows old "PyConDE PyData" signage or an unflattering moment. Choose photos by eye.
- **Long titles:** a very long talk title on a narrow card is set small but correctly. The engine reports these with `weak hierarchy` in its notes.

## Tests

```bash
uv run --extra cards pytest tests/test_social_cards.py
```

The suite checks the palette against the website CSS and the line breaker on known cases. Each validation rule gets a deliberately broken composition and must reject it.
Every fixture card in every format must produce a valid design, and the output must be deterministic. The talk-card cache must redraw only cards whose content changed. The full run takes about 80 s.
