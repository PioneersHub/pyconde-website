# Pretalx import

Session and speaker data are sourced from Pretalx via two importers. Talk and speaker `contents.lr` files are **generated**; do not edit them in this repository — the next import overwrites them.

## Pipeline

```text
Pretalx CFP API ──→ utils/talks.py     ──→ content/<edition>/talks/<slug>/contents.lr
                ──→ utils/speakers.py  ──→ content/<edition>/speakers/<CODE>/contents.lr
```

`<edition>` is `/talks/` for the current edition and `/archive/{year}/talks/` for archived ones.

Both importers read year-keyed config from `databags/pretalx.yaml`. Each edition has its own Pretalx event slug, question IDs, and submission-type IDs — those drift between events, so the mapping must be explicit, not heuristic.

```yaml
# databags/pretalx.yaml — abridged
editions:
  2026:
    event_slug: pyconde-pydata-2026
    question_ids:
      python_skill: 12345
      domain_expertise: 12346
      pronouns: 12347
    submission_type_ids:
      talk: 100
      keynote: 101
      tutorial: 102
```

When importing a new edition, fill in the year block by inspecting the Pretalx event in the admin UI — the question and submission-type IDs are visible in their URLs.

## Run an import

Set `PRETALX_API_KEY` in `.env` first.

```bash
uv run python utils/talks.py     --year 2026
uv run python utils/speakers.py  --year 2026
```

`--year` accepts a four-digit year or `current`. Both importers:

- Use Pretalx's `?expand=` parameter to fetch related answers in fewer requests.
- Throttle between paginated calls (Pretalx's rate limit is shared with other tooling).
- Run sequentially, not in parallel — Pretalx is upstream of multiple services.
- Are idempotent — re-running overwrites generated fields but preserves the slug field on talks once written.

## Speaker bios

**Bios are never rewritten.** The importer writes the bio exactly as Pretalx returned it.

If the bio is in first person (regex check: a stand-alone `I`, possibly with an apostrophe), the importer prepends a single framing line so the bio reads as a quote rather than as editorial copy:

```markdown
_This is what {first_name} says:_

I'm a data scientist at …
```

This rule is intentional and protects speaker voice — bio bodies are never re-phrased. See the importer source for the exact regex if the detection misses an edge case.

## Talk-folder naming

After import, the slug migration renames each talk folder from `{CODE}` to its slug-form (see [docs/archive.md](archive.md)). The current importer still writes folders by `{CODE}` for fresh imports; running `utils/migrate_pretalx_slugs.py` afterwards is required before deploy.

Open item: extend `utils/talks.py` to write directly to slug-folders, so the explicit migration step disappears.

## Automated runs

`.github/workflows/fetch_submissions.yml` runs the importers on a schedule. The cron is paused outside conference cycles — re-enable it by uncommenting the `schedule:` lines when the next CFP closes. Manual runs via `workflow_dispatch` are always available.

The workflow's trigger policy is deliberate: **only `schedule:` and `workflow_dispatch:`**. Wiring it to `push:` would cause every commit to main to hit the Pretalx API and race with the deploy in `main.yml`.

## Common follow-ups

| Symptom | Fix |
|---|---|
| Wrong skill / expertise / pronoun values | Question ID drifted; update `databags/pretalx.yaml` for the year |
| Missing talk after import | Talk is not `confirmed` in Pretalx, or has a submission type not listed under `submission_type_ids` |
| Speaker bio shows as third-person but reads first-person | Regex didn't catch the bio's `I` (e.g. due to leading whitespace or markdown emphasis). Re-import or hand-edit the framing if needed — never rewrite the bio body |
| Rate-limit errors from Pretalx | Lower the import frequency, run editions sequentially, or contact Pretalx support |
