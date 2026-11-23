# Social Cards

Social cards (og:image, feed posts, stories) are designed by an engine in `utils/social_cards/`. It does not fill templates.
For every card it builds many brand-compliant layouts, rejects any that break a brand rule, scores the rest and refines the best few. Then it exports the winner.

Cards reach the site, and the sponsors, in four ways:

- **Talks:** `make fetch-submissions` draws a card for every talk from Pretalx data.
- **Site pages** (blog posts, masterclasses, call and info pages): `make page-cards`, see [Page cards](#page-cards).
- **Campaign cards** for social posts: written by hand in a card file and rendered with `make social-cards`, see [Card files](#card-files).
- **Sponsor cards in Google Drive** (all four formats, for sponsors and social media): `make sponsor-cards-upload`, run by hand,
  see [Sponsor cards in Google Drive](#sponsor-cards-in-google-drive).

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

### Previewing and tuning

```bash
make card-preview
```

This builds a gallery in `build/card-preview/index.html` (not committed). It covers every card in `tests/social_cards/cards.yaml` and every page card,
sponsor cards included. Each card is shown on every background its category draws from, in every format. The card's own background is
outlined. For each cell you see the card the engine picks, every other candidate with its critique scores, and every rejected variant
with the rule it broke. Pages that cannot get a card at all are listed at the top.

To tune, edit `utils/social_cards/brand.yaml`, run it again and reload. A full run takes several minutes. To redo a few cards, run
`uv run --extra cards python utils/card_preview.py --only sponsors/lidl,news-short`. In the Claude desktop app the gallery is served by
the `card-preview` entry in `.claude/launch.json`. Elsewhere, open the file directly.

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
    event: masterclasses       # whose dates the footer shows: conference (default) | masterclasses
    sponsor_logo: assets/static/media/sponsors/lidl.svg   # sponsor cards: SVG or transparent PNG
    dates:                     # rows for the key-dates layout
      - {date: 19 April 2027, label: Masterclasses & DjangoGirls}
```

The text is used exactly as written. The engine chooses line breaks and sizes, but it never shortens, rewords or reorders content. A missing required field or an unknown key is an error.

Event facts are never written into a card file. "PyCon DE 2027", the dates and the venue come from `databags/branding.yaml`.

Formats: `og` (1200×630, exported at 2×, the size `templates/layout.html` announces), `square` (1080²), `portrait` (1080×1350), `story` (1080×1920, with text kept clear of the platform UI).

## Content families

### Background colours

Every card, of every kind, gets one of the four primaries blue, green, orange or yellow as its background (`backgrounds` in `brand.yaml`).
The style guide makes a brand surface one solid primary; cyan and lime are left out until card text and logo rules exist for them.

Sponsor cards are the exception: they always use the warm off-white of the website's sponsor section (`#f7f5ee`), on which sponsor logos keep
their own colours. A category names such an exception in its own `backgrounds`.

The colour is picked from a hash of the card's id (the page path, or the talk code). It looks random across cards, but a card keeps its
colour on every run, so it is redrawn only when its content changes. To change which colours are used, edit `backgrounds`.
That changes the brand spec, so every generated card is redrawn on the next run.

### Layout signatures

Colour does not tell content types apart; layout does. Each content type keeps one layout signature, so a reader scrolling a feed can
tell a talk from a masterclass or a blog post on any colour. The engine varies only type and composition inside a family:

| Content | Category | Signature | Taken from the website |
| --- | --- | --- | --- |
| Talks | `talk` | Coloured spine on the left, "Talk" | Session cards (§06) |
| Keynotes | `keynote` | Speaker photo; "Keynote" | Keynote section |
| Masterclasses | `masterclass` | "Full-Day / Half-Day Masterclass", trainers, monogram in a corner | Masterclass section |
| Blog posts | `news` | Python artwork, "News" | Blog-card fallback (§05) |
| Other pages | `page` | Large monogram beside or above the title, no kicker | Site intro |
| Sponsors | `sponsor` | "Thank you for your support!", the tier as kicker, the sponsor's logo as the hero, monogram bottom right, on the warm off-white | Sponsor wall; the 2025 thank-you banners |

The families are set in `categories` in `utils/social_cards/brand.yaml` (strategies and pinned logo placements).
Campaign categories (`cfp`, `tickets`, `sponsorship`, `community`, …) keep a wider choice of layouts, because each campaign card is art-directed on its own.

## Page cards

`make page-cards` brings the card of every eligible page up to date. It is safe to run at any time and touches only cards that are out of date.
Run it after adding or retitling a page.

### Which pages get a card

`utils/social_cards/pages.yaml` holds one recipe per page model: the category (and so the family) and the page fields that fill the card.

| Page model | Family | Card shows |
| --- | --- | --- |
| `blog-post` | news | `title` |
| `masterclass` | masterclass | `title`, `trainer`, "Full-Day/Half-Day Masterclass" from `hours`, the masterclass day |
| `keynote` | keynote | `title`, `speaker_name` |
| `call-for-proposals`, `financial-aid`, `standard-page`, `media-kit` | page | `title` |
| `sponsor` (preview only, see below) | sponsor | "Thank you for your support!", `type` (the tier), `logo` |

Every card also shows "PyCon DE 2027" with the dates and venue from `databags/branding.yaml`: the conference dates, or the masterclass day.
Nothing else on a page reaches its card.

Not included:

- **Talks** have their own generator (`make fetch-submissions`).
- **Archive pages** (`content/archive/`) keep their cards.
- **Sponsor pages** are listed in `preview_only` in `pages.yaml` while their thank-you design is being confirmed. `make card-preview`
  shows them, but `make page-cards` does not draw them, so the site keeps its default card. To publish them, remove `sponsor` from
  `preview_only` and run `make page-cards`.
- **Pages whose model has no `social_card_image` field** (FAQ, tickets, sponsoring, newsletter, …) use the site's default card.
  To include one, add the field to its model in `models/` and a recipe to `pages.yaml`.

The card is saved next to the page as `social_card.png`. The page gets `social_card_image: /<path>/social_card.png` if it does not have it yet;
no other line of the page changes. Pages are treated as English; `page_lang` in `pages.yaml` lists the exceptions (the German terms page).

### When a card is redrawn

Each generated card stores a record inside the PNG: what is printed on it (category, headline, names, kicker, dates, venue, event name),
a fingerprint of `brand.yaml`, and a checksum of its pixels. The record is PNG metadata, so no extra file is published.
On every run the generator builds the record from the page and `branding.yaml` again and compares:

| Situation | Result | Reported as |
| --- | --- | --- |
| No `social_card.png` yet | Card drawn | `drawn` |
| Record matches | File left untouched | `up to date` |
| Something printed on the card changed (title, names, `hours`, dates, venue) | Card redrawn | `redrawn: headline changed` (lists every change) |
| `brand.yaml` changed | Card redrawn | `redrawn: spec changed` |
| Page not yet linked to its card | `social_card_image` added | `…, linked as /<path>/social_card.png` |

Other edits (body, description, tags, a masterclass's time of day) do not redraw a card. Changes to the engine's code alone do not either:
to refresh a card after such a change, delete its `social_card.png` and run again.

A page that cannot get a card is reported as `failed: …` and keeps whatever it had; the other pages are still processed and the run ends with an error.
This happens when a field the recipe needs is missing, when a masterclass's `date` names another day than `branding.yaml` or its `hours` is not 6 or 3,
when no design passes the brand checks (e.g. a title containing "PyCon DE & PyData", the archive-only name), or when the page file cannot be rewritten safely
(usually a missing final newline; add one and run again).

### Hand-made cards are never replaced

A card is hand-made when the generator did not draw it, or when it was changed after the generator drew it. In practice:

- any `social_card_image` other than `/<path>/social_card.png`, or
- a `social_card.png` without the generator's record, or whose pixels no longer match the stored checksum. An image edited in place counts,
  even if the editing tool kept the metadata.

The generator never overwrites, deletes or relinks a hand-made card, and it never touches the page of one. The run reports it as `kept: …`.
When the title of such a page changes, update the hand-made card yourself.

**To replace a generated card with your own**, pick one:

- **Overwrite `social_card.png`** with your file (1200×630 or 2400×1260 PNG) and commit. Nothing else to change; the page already points to it.
  From then on the run reports `kept: social_card.png is hand-made or was edited by hand`.
- **Use another file name**: save it as, say, `card.png` in the page folder, set `social_card_image: /<path>/card.png`,
  and delete the generated `social_card.png`, which would otherwise still be published. The run reports `kept: social_card_image points to …`.

**To go back to a generated card**, delete your file, point `social_card_image` back to `/<path>/social_card.png` (or remove the line),
and run `make page-cards`.

### Sponsor logos

A sponsor's logo is shown in its own colours and proportions, never recoloured, cropped or distorted. In each format every logo gets
the same area (`sponsor_logo.area` in `brand.yaml`), so a square mark and a long wordmark carry the same weight. Its clear space is reserved
around it. A layout that would shrink a logo below 85 % of that area is not used. On og cards compact logos therefore sit beside the
thank-you, and long wordmarks sit under it, across the full width. A wordmark so long that it would be thinner than the minimum height is
raised to that height.

The thank-you spans the full width; on square, portrait and story cards it always takes two large lines ("Thank you / for your support!").
The PyCon DE monogram signs the card at the bottom right, beside the event facts.

A logo file is refused, with the reason, when the card renderer cannot show it faithfully:

- an SVG that sets its text in a font (`<text>`): ask the sponsor for a version with outlined text, or use a transparent PNG;
- an SVG the renderer cannot size (no `viewBox`);
- a PNG with an opaque background, or one that would be enlarged more than 1.5×;
- a logo that would nearly vanish on the off-white (less than 10 % of it stands out).

The page then gets no card and is listed in the preview. In November 2026 this applied to Academis and PyData Berlin (text in a font)
and Python4DataScience (no `viewBox`). The rules are in `sponsor_logo` in `brand.yaml`.

### Sponsor cards in Google Drive

The site only uses the og card. Sponsors and the social-media team get every sponsor's thank-you card in all four formats
in the shared sponsor-cards folder in Google Drive:

```bash
make sponsor-cards-upload
```

**This is a local process.** Neither the site build nor CI runs it, and nothing it writes is committed. Run it after a sponsor is
added, a logo or tier changes, or the card design is tuned.

It draws each sponsor's card in og, square, portrait and story into `build/sponsor-cards/` and uploads them, one subfolder per sponsor:

```text
<slug>/<slug>_og.png
<slug>/<slug>_square.png
<slug>/<slug>_portrait.png
<slug>/<slug>_story.png
```

`<slug>` is the sponsor's folder under `content/sponsors` (`lidl`, `mm-software`, `schwaebisch_hall`). A rerun replaces files of the
same name, so Drive never holds two versions of a card. A sponsor whose card cannot be drawn in every format (see the refusals above)
is listed at the end and left out; the others are still uploaded and the run exits non-zero. The Drive folder and the page model are
set under `drive_upload` in `utils/social_cards/pages.yaml`. Sponsor cards are drawn even while `sponsor` is listed in `preview_only`.

It signs in to Drive exactly as `make sponsor-assets` does, with the same Google OAuth client and the same Drive token
(`drive_token_json` in your pytanis config, see [Sponsors & partners](sponsors_partners.md)). That token holds full Drive access:
the narrower `drive.file` scope cannot add files to a folder the tool did not create. A token from before, granted read-only access,
is replaced: the next run of either command asks you to approve full access once.

## How a card is designed

| Step | Module | What happens |
| --- | --- | --- |
| Brand spec | `brand.yaml`, `brand.py` | Palette, approved field/text pairs, type roles, logo files, categories. Event facts come from `branding.yaml` |
| Content | `content.py` | Card model and analysis (speakers, image, dates, CTA) |
| Candidates | `layouts/` | Six strategies (below) × variants, on the card's background |
| Typesetting | `fonts.py`, `typeset.py` | HarfBuzz shaping, exhaustive line-break search, discrete size steps, optical margin alignment |
| Validation | `validate.py` | Hard brand and geometry checks; one violation rejects the candidate |
| Critique | `critique.py` | Typography 35, composition 25, hierarchy 20, colour 10, refinement 10 |
| Refinement | `pipeline.py` | Local search around the best four candidates (size step, measure, logo scale, art share) |
| Export | `render.py` | SVG with text as glyph outlines and the official logo SVG embedded verbatim, rasterised by resvg with system fonts disabled |

The output is deterministic: the same card file renders to the same bytes. Variation between cards comes from a seed derived from the card id, and from a penalty for repeating the previous card's composition.

### Strategies

| Strategy | Source on the website | Used for |
| --- | --- | --- |
| Field | Intro, tickets, sponsoring, newsletter, masterclass sections | Masterclasses, other pages, announcements, CfP, tickets, sponsoring, community, keynotes |
| Spine | Session cards (§06 accent bar); the spine never takes a colour forbidden on the background | Talks, speaker spotlights |
| Python | Blog-card fallback (§05); only pythons with no segment in the background colour | News, announcements, schedule |
| Portrait | — (no 2027 photo rule yet, see below) | Cards that come with a photo |
| Dates | Key-dates band | Important dates |
| Thanks | Sponsor wall: logo in its own colours on the off-white | Sponsor thank-you cards |

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
- the python artwork (§05);
- one solid primary as a brand surface's background (`flags` in `design-system.json`);
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
uv run --extra cards --extra drive pytest tests/test_sponsor_cards_drive.py
```

The suite checks the palette against the website CSS and the line breaker on known cases. Each validation rule gets a deliberately broken composition and must reject it.
Every fixture card in every format must produce a valid design, and the output must be deterministic. The talk-card cache must redraw only cards whose content changed. The full run takes about 80 s.
