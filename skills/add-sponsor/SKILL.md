---
name: add-sponsor
description: Add a confirmed sponsor or partner of the current PyCon DE edition to the website from its Google Drive folder (logo plus a document with website, social links and description). Use when asked to "add a sponsor", "add <company> as Gold/Silver/… sponsor", or given a link to a folder in "Sponsors 2027".
---

# Add a sponsor from Google Drive

The sponsor pipeline is documented in `docs/sponsors_partners.md`; read it first. This skill covers the steps around it: getting the material from Drive and shipping one reviewed pull request.

## Requirements

- **`make sponsor-assets`** (`utils/drive_fetch.py`) reads the folder through the Google Drive API with read-only access.
  It needs the `drive` extra (`uv run --extra drive` installs it) and a pytanis config (`~/.pytanis/config.toml` or `$PYTANIS_CONFIG`) whose `[Google]` section names
  `client_secret_json` and `drive_token_json`. The first run opens a browser for the user's consent; tell the user to approve it, never click through it yourself.
  If the script stops with a configuration error, report it and let the user fix the config.
- **Fallback** when the API can't be used: ask the user to copy the logo into `assets/static/media/sponsors/`
  of their checkout and paste the document text into the chat. Do not drive the user's browser to scrape Drive.
- Read access to the sponsor folders. Each confirmed sponsor has its own folder in the shared folder **Sponsors 2027**, named `<Tier> - <Company>`,
  for example `Gold - STAT-UP Statistical Consulting & Data Science GmbH`.

## Inputs

The user names the sponsor or gives the folder link. Everything else comes from the folder:

| Item | Where it is | Required |
| --- | --- | --- |
| Tier | Folder name prefix (`Gold`, `Silver`, …), or the user | yes |
| Company name | Document title / first line | yes |
| Logo | Image file in the folder; SVG preferred, PNG accepted | yes |
| Website | `Website:` line in the document (the link target, if the line is linked text) | yes |
| Social links | `LinkedIn:`, `Instagram:` lines in the document | no |
| Description | Text after `Description:` in the document | yes |

If a required item is missing or two candidates conflict (two logos, two websites), stop and ask. Never fill a gap with text from the sponsor's website or from a past lineup unless the user says so.

## Steps

1. **Branch from the latest `main`**: `git fetch origin && git switch -c <prefix>/add-<sponsor-id> origin/main`.
2. **Fetch the folder**: `make sponsor-assets FOLDER=<folder-link>`. It saves the logo files (SVG, PNG, JPEG) to `assets/static/media/sponsors/`
   under a URL-safe version of their names (it prints any renaming), refuses SVGs containing script or event handlers, and stops rather than
   overwrite an existing logo. Each Google Doc is printed as Markdown, so a linked text such as `[Company](https://…)` shows its URL:
   take the website from the link target, and drop Markdown escapes such as `\&` when copying text.
3. **Check the logo**: note the aspect ratio. Logos wider than about 5:1 render very small in the fixed logo boxes of the sponsor wall;
   tell the user and suggest asking the sponsor for a more compact variant.
4. **Add the entry** to `databags/sponsors.yaml` under the tier's `sponsors:` list (append unless the user gives a position):
   - `id`: lower-case slug of the short company name, unique across the file; it becomes `/sponsors/<id>/`.
   - `name` and `headline`: the full company name.
   - `description`: the document text **verbatim**, as a `|` block. Separate paragraphs with `<br/><br/>` at the end of a paragraph followed by a blank line, like the other entries.
     Do not fix wording or typos silently; point them out to the user instead.
   - `website`: full URL with `https://`.
   - `social`: profile URLs as given. Only hosts in `SOCIAL_PLATFORMS` (`utils/sponsors.py`) are accepted, subdomains such as `de.linkedin.com` included.
     For a new platform, add it there and an icon to `assets/static/media/social/` first.
   - `logo`: `/static/media/sponsors/<file>`; `scale: null`.
   - If the sponsor appears in a past lineup (`databags/sponsors_20xx.yaml`), keep its `id` so the past sponsors strip and featured list stay consistent.
5. **Generate the sponsor page**: `make sponsor-pages`. It validates the file and adds `content/sponsors/<id>/contents.lr` to git; only the new sponsor's files should change.
6. **Verify text**: compare the description in `sponsors.yaml` with the document, ignoring line wrapping and the `<br/><br/>` breaks. They must be identical.
7. **Check locally**: `BUILD_MODE=current uv run lektor server -p 5050`, then look at
   - `/sponsors/`: the logo appears in its tier row, is legible on the section background and links to the sponsor page;
   - `/sponsors/<id>/`: tier label, logo card, website button, social icons and paragraphs.
8. **Lint** changed Python with `uv run ruff check` and `uv run ruff format --check`, and changed Markdown with `npx markdownlint-cli2`.
9. **Commit and open a pull request** against `main` with the user's approval. List in the description what came from the Drive folder, anything you could not verify, and any issue you noticed (typos in the text, a very wide logo).

## Don'ts

- Don't edit the frozen past lineups `databags/sponsors_20xx.yaml`.
- Don't hand-edit `content/sponsors/*/contents.lr`; regenerate them.
- Don't add a share image path; `make sponsor-pages` links `content/sponsors/<id>/social_card.png` only once that file exists.
