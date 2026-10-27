# Sprint projects

Sprints run on the two days after the conference (2027: Friday–Saturday, 23–24 April). Project leads propose a sprint through the form linked on `/sprints/`,
and each accepted project is listed with its logo. This page is the recipe for adding one. It is written so that a person or a coding agent can follow it step by step.

## Where things live

| What | Where | URL |
| --- | --- | --- |
| Accepted projects list | `content/sprints/contents.lr`, section `## Accepted Projects` | `/sprints/#accepted-projects` |
| Front-page "Sprints" block | `databags/frontpage/sections/initiatives.yaml`, first block, `committed:` list | `/#initiatives` |
| Sprint logos | `assets/static/media/sprints/<project>.svg` | `/static/media/sprints/<project>.svg` |
| Logo tile styling | `assets/static/css/custom.css`, rules under `.subsite #accepted-projects` and `.initiatives__logo` | — |

Both lists are kept by hand, so a new project has to be added in two places: the sprints page and the front page.

## Get the logo

1. **Use the project's official logo.** Look for a brand, design or press page on the project's website, or a `design`/`branding` repository on GitHub. Example: Project Jupyter's logos live in [jupyter/design](https://github.com/jupyter/design).
2. **Prefer SVG.** Use PNG only if the project offers no SVG.
3. **Prefer the wide logo with the wordmark** (icon plus name). The tiles are wider than they are tall, so a wide logo reads better than the icon alone.
4. **Pick a variant that works on white.** Both lists show logos on a white tile, so a white or light "for dark backgrounds" variant would be invisible.
5. **Check the file before committing it.** An SVG can carry scripts. This must print `0`:

   ```bash
   grep -ciE "<script|javascript:|on[a-z]+=" assets/static/media/sprints/<project>.svg
   ```

6. **Save it as** `assets/static/media/sprints/<project>.svg`, with a lowercase, hyphenated name (`scikit-learn.svg`, `jupyter.svg`).

If the logo is already on the site, reuse it instead of copying it. spaCy, for example, points at its sponsor logo in `/static/media/sponsors/`.

## Add a project

1. **Sprints page.** In `content/sprints/contents.lr`, add a line at the end of the `## Accepted Projects` list. The logo and the name both link to the project; the tagline is a few words on what the project does:

   ```markdown
    * [![Project Jupyter](/static/media/sprints/jupyter.svg)](https://jupyter.org/) [Project Jupyter](https://jupyter.org/) — interactive computing across many languages
   ```

   Keep the leading space before `*`, as in the existing lines. The list is in the order projects were confirmed, so new projects go last.

2. **Front page.** In `databags/frontpage/sections/initiatives.yaml`, add an entry at the end of the `committed:` list of the `Sprints` block. Use the same name, URL and logo path:

   ```yaml
         - name: "Project Jupyter"
           url: https://jupyter.org/
           logo: /static/media/sprints/jupyter.svg
   ```

   `name` becomes the logo's alt text. Without `logo`, the name is shown as text.

## Check it

Build the current edition and serve it locally:

```bash
BUILD_MODE=current uv run lektor build -O site --no-prune
```

```bash
uv run python -m http.server 8000 --bind 127.0.0.1 --directory site
```

Then open:

- `http://127.0.0.1:8000/sprints/#accepted-projects` — the new line shows the logo on its white tile, next to the link and tagline.
- `http://127.0.0.1:8000/` — scroll to "Sprints, Hackathons & Initiatives"; the logo appears in the Sprints block under "Committed".

Both tiles fit the logo into a fixed box without cropping it. If the logo looks tiny, the SVG probably has a lot of empty space around the artwork. Try another variant from the project, or ask the project for one.
