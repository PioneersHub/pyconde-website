# Masterclasses

Masterclasses are paid workshops on the day before the conference (2027: Monday, 19 April). Trainers propose them through a Google Form,
the Masterclass Committee picks them, and each accepted class gets its own page on the site. This page is the recipe for adding one. It is written so that a person or a coding agent can follow it step by step.

## Where things live

| What | Where | URL |
|---|---|---|
| One page per masterclass | `content/masterclasses/<slug>/contents.lr` (model `masterclass`, template `masterclass.html`) | `/masterclasses/<slug>/` |
| Overview with one card per masterclass | `content/masterclasses/contents.lr` (model `masterclasses`, template `masterclasses.html`) | `/masterclasses/` |
| Call for Masterclasses | `content/masterclasses/call/contents.lr` (model `call-for-proposals`) | `/masterclasses/call/` |
| Homepage carousel | `databags/frontpage/sections/masterclasses.yaml`, switched on in `databags/frontpage/config.yaml` | `/#masterclasses` |
| Masterclass day (JSON-LD start date) | `databags/branding.yaml` → `dates.masterclasses_iso` | — |

The overview lists every child page with model `masterclass`, sorted by title. The call page sits in the same folder but is filtered out of the cards.
The homepage carousel is a hand-kept list, so a new masterclass has to be added in two places: its page, and the carousel.

## Formats

| Format | `date` field | `hours` field |
|---|---|---|
| Full-day | `Monday, 19 April 2027, 9:00–16:00 (lunch break 12:00–13:00)` | `6` |
| Half-day, morning | `Monday, 19 April 2027, 9:00–12:00 (morning)` | `3` |
| Half-day, afternoon | `Monday, 19 April 2027, 13:00–16:00 (afternoon)` | `3` |

Copy the `date` string exactly, with en dashes (`–`). It is shown verbatim on the page header and the overview card. `hours` must be a bare number: the page header renders it as "· 6 hours", and the JSON-LD turns it into `PT6H`.

## Input: the proposal form

Proposals arrive in the form's response sheet ("Proposal for a PyConDE 2027 Masterclass (Responses)"). Only the columns marked "for the conference website" go on the site:

| Sheet column | Goes to |
|---|---|
| Your name | `trainer` field, and the "Your trainer" heading |
| Title of your masterclass | `title` field |
| A summary of your masterclass | Body intro |
| Target audience | Body, "Who Should Attend" |
| Goals: What learning outcomes can participants expect? | Body, "What You'll Learn" |
| Technical requirements for participants | Body, "What to Bring" |
| Short speaker bio | Body, "Your trainer: …" |

Do **not** publish the email address, training methods, timeline, or room requirements. Those are for review and organisation only.

## Add a masterclass

1. **Pick the slug:** `<title>-<trainer>`, lowercase ASCII, words joined by hyphens, accents dropped. Example: "Rust for Python developers" by Rodrigo Girão Serrão → `rust-for-python-developers-rodrigo-girao-serrao`.

2. **Create the page** at `content/masterclasses/<slug>/contents.lr`. Fields are separated by lines with `---`. For `tags`, leave a blank line after `tags:` and put one tag per line.

   ```text
   _model: masterclass
   ---
   title: Rust for Python Developers
   ---
   description: Learn the fundamentals of Rust — compilation, ownership and borrowing, errors, enums and structs — and call your Rust code from Python with PyO3.
   ---
   meta_title: Rust for Python Developers — Full-Day Masterclass
   ---
   trainer: Rodrigo Girão Serrão
   ---
   date: Monday, 19 April 2027, 9:00–16:00 (lunch break 12:00–13:00)
   ---
   hours: 6
   ---
   tags:

   Rust
   PyO3
   Performance
   ---
   body:

   <summary from the form>

   # Who Should Attend

   <target audience from the form>

   # What You'll Learn

   * <one bullet per learning goal>

   # What to Bring

   <technical requirements from the form>

   # Your trainer: Rodrigo Girão Serrão

   <bio from the form>

   ---
   notes:
   ```

   Field rules:

   - `title`: the title from the form, in title case. Keep a project's own spelling, e.g. "pytest" stays lowercase.
   - `description`: 110–160 characters. It is used for social sharing and on the overview card.
   - `meta_title`: 50–60 characters, e.g. `<Title> — Full-Day Masterclass` or `<Title> — Half-Day Masterclass`.
   - `trainer`: the name exactly as given in the form. For two trainers, write `Name One & Name Two`.
   - `date` and `hours`: copy them from [Formats](#formats).
   - `tags`: 3–4 short topic tags.
   - Body: start with the summary. Do not repeat the page title; the template already renders it as the page's single `h1`.
   - Body headings: use `#` for peer sections and the trainer heading, and `##` for any nested subsection. The template's `shift_headings` filter renders these as `h2` and `h3`, respectively.
   - `notes`: leave it empty.

3. **Edit the trainer's text lightly.** Keep their wording and voice, including a bio written in the first person. Do only these:
   - Turn lists into Markdown bullets.
   - Format code names as code, e.g. `` `tmp_path` ``.
   - Fix obvious typos.
   - Make every link absolute. Bios copied from a personal site often have relative links like `/blog`, and those break on our site.
   - Check that every link resolves, e.g. `curl -s -o /dev/null -w '%{http_code}' -L <url>` should print `200`.

4. **Add a carousel card** to `items:` in `databags/frontpage/sections/masterclasses.yaml`. The list order is the carousel order.

   ```yaml
     - id: rust                       # unique, short
       type: masterclass
       name: "Rodrigo Girão Serrão"
       title: "Rust for Python Developers"
       teaser: "Write your first Rust programs, master ownership and borrowing, and call Rust from Python with PyO3."
       image: ""
       image_alt: ""
       link_text: "Details & booking"
       link_url: /masterclasses/rust-for-python-developers-rodrigo-girao-serrao/
   ```

   Keep `teaser` to one sentence of about 80–120 characters.

5. **Social card (optional).** Put a 16:9 PNG at `content/masterclasses/<slug>/social_card.png` and add `social_card_image: /masterclasses/<slug>/social_card.png` to the page. Without it, the page uses the site's default card.

6. **Check it locally.**

   ```bash
   BUILD_MODE=current uv run lektor server -p 5791
   ```

   - `/masterclasses/<slug>/`: the header shows the date and "· 6 hours" (or "· 3 hours"), and the tags render.
   - `/masterclasses/`: the new card is there, and the call page is not a card.
   - `/#masterclasses`: the carousel shows the new card and its link works.
   - The page's JSON-LD (`"@type": ["Course", "EducationEvent"]`) has `startDate` equal to `dates.masterclasses_iso` and `courseWorkload` `PT6H` or `PT3H`.

   Then run `BUILD_MODE=current uv run lektor build -O site --no-prune` and make sure it finishes without errors.

7. **Commit and open a PR.** One commit per batch of masterclasses is fine.

The homepage carousel only shows when `masterclasses` has `display: true` in `databags/frontpage/config.yaml`. It is on while masterclasses are being sold.

The carousel heading ends with a "Propose a masterclass →" link to the call (`header_link_text` and `header_link_url` in the same databag). Remove both lines when the call closes.

## When times, prices or rules change

The masterclass times, prices and switching rule appear on several pages as plain text. Change all of them together:

| Text | Files |
|---|---|
| Times for full-day and half-day classes | `content/masterclasses/call/contents.lr`, `content/masterclasses/contents.lr`, `content/buy-ticket/contents.lr`, `databags/faq.yaml` and `databags/faq_tickets_de.yaml` (`on-site-tickets-pricing`), every masterclass page's `date` |
| Prices | `content/buy-ticket/contents.lr` (Masterclasses section), `databags/faq.yaml` and `databags/faq_tickets_de.yaml` (`on-site-tickets-pricing` table) |
| Switching classes (deadline, how) | `databags/faq.yaml` and `databags/faq_tickets_de.yaml` (`switch-masterclass`). The ticket page and the overview link to this FAQ entry and don't repeat the rules. |
| "First masterclasses, more will follow" | `content/masterclasses/contents.lr`, `content/buy-ticket/contents.lr`, both FAQs, `header_teaser` in `databags/frontpage/sections/masterclasses.yaml` |
| Masterclass day | `databags/branding.yaml` (`dates.masterclasses`, `dates.masterclasses_iso`), the call page, every masterclass page's `date` |

Write all prices with a euro sign and a space, e.g. `690 €`.

## Common follow-ups

| Symptom | Fix |
|---|---|
| New page is missing from the overview | `_model` is set to something other than `masterclass`, or the folder is not directly under `content/masterclasses/` |
| Call page shows up as a card | The `_model: call-for-proposals` line is missing from `content/masterclasses/call/contents.lr`. Pages under `/masterclasses/` default to `masterclass`, so the call needs that line. |
| Header says "· 2 x 3.5 hours" or JSON-LD has a strange `courseWorkload` | `hours` is not a bare number |
| Homepage has no masterclass carousel | `masterclasses` is `display: false` in `databags/frontpage/config.yaml` |
| Carousel card links to a 404 | `link_url` does not match the folder name, or is missing the trailing slash |
| A removed masterclass is still online | Deploys never delete. Remove the object from the bucket, see [deployment.md](deployment.md). |
