# Selective Builds — Current Edition Fast, Archives On Demand

> Hand-off brief, companion to `content-strategy.md`. Status: **implemented
> and locally verified** (2026-07-02).
>
> **Amended 2026-08-05.** Two things below are no longer true as written, and
> the sections concerned have been corrected in place:
>
> 1. **Attendee certificates are out of scope.** `content/attendee-certificate/`
>    was moved to `content-archived/` in `b00f336e`, so it no longer builds in
>    any mode and has been removed from `databags/selective_build.yaml`.
>    `/attendee-certificate/{uuid}/` URLs are not served.
> 2. **Deploy targets are now a list, not a bucket.** Both syncs go through
>    `utils/deploy_to_s3.py`, which fans out to every bucket in
>    `databags/deploy_targets.yaml`. `jakejarvis/s3-sync-action` is gone.
>    Each bucket receives a complete, independent copy — this document's
>    "the S3 sync never deletes, so previously deployed pages stay live"
>    property now has to hold *per bucket*, which is what it failed to do
>    when a second bucket was added to one workflow only.
> 3. **The `archive` / `full` build-mode choice no longer reaches CI.** The
>    archive workflow always builds `full` and narrows the *upload* with
>    `--year`. Build scope and deploy scope are now separate knobs: a
>    year-scoped render would leave Pagefind indexing a fraction of the site
>    and overwrite the complete index, so only the upload is scoped. See
>    Deploy semantics below.

## TL;DR

Production deploys build **only the current edition** (~600 pages, incl. the
blog — it covers only the current conference). Archive editions (~2,500 pages)
are static after their initial generation — they get built **only on demand**,
all past editions at once, via a manually dispatched GitHub Actions workflow.
Because the S3 sync never deletes, previously deployed archive pages **stay
live** even when a deploy omits them — in each bucket that has received an
archive deploy at least once. See Deploy semantics.

The critical design property (learned the hard way in review): the filter
applies to the **build traversal, not record discovery** — every page that
does render (homepage, sitemap segments, topic hubs, `llms.txt`) still sees
the full record tree and renders **byte-identically in every mode**. Modes
only decide *which* artifacts get built, never what they contain. The one
exception is the Pagefind search index, which runs only in `full` builds.

## Measured facts (2026-07-02)

| Metric | Value |
| --- | --- |
| Built HTML pages, total | 5,017 |
| — of which `/archive/` | 2,484 (49.5%) |
| — of which `/attendee-certificate/` | 1,930 (38.5%) |
| — current edition + misc | ~600 (12%) |
| `site/` output size | 486 MB |
| `content/archive/` source | 27 MB (8 editions: 2016–2019, 2022–2025) |
| `content/attendee-certificate/` source | 8.3 MB |
| Warm local build (`make build`, incremental) | ~12 s |
| **Cold render, `BUILD_MODE=full`** | **106 s** (5,017 pages) |
| **Cold render, `BUILD_MODE=current`** | **22 s** (603 pages) — ~5× faster, plus Pagefind skipped entirely |

Lektor builds incrementally, so local rebuilds are already cheap. The cost is
in CI: every Actions run starts from a cold checkout and re-renders all 5,017
pages, then Pagefind re-indexes 486 MB. **88% of that work produces pages that
have not changed since they were archived.**

## Build modes

Controlled by a `BUILD_MODE` environment variable, default `current`.

| Mode | Scope | Trigger |
| --- | --- | --- |
| `current` | Current edition: `/`, `/talks/`, `/speakers/`, blog (per-year, current conference only), pages | Every push to `main` (production) and every PR (staging) |
| `archive` | All past editions under `/archive/` | Manual dispatch (`archive-build.yml`) |
| `full` | Everything — the only mode that regenerates cross-edition outputs | Manual dispatch; run after archiving an edition or changing shared templates |

Per-year archive builds were considered and rejected — a single `archive` mode
rebuilding all past editions (~2 min) is simpler and has fewer edge cases.

## Mechanism — Lektor plugin

New plugin `packages/selective-build/` (auto-loaded from `packages/`, same
pattern as `packages/yaml-databags/` — no `.lektorproject` change needed).
It wraps `PageBuildProgram.iter_child_sources` — the point where
`build_all` descends into child records — so excluded subtrees never enter
the **build queue**. Template queries (`Database.iter_items`, `.children`,
`site.get(...)`) stay untouched: every page that renders sees the full
record tree.

> An earlier iteration filtered `Database.iter_items` (record discovery)
> instead. Adversarial review killed it: the homepage's latest-videos
> section walks `site.get('/archive').children` at render time and rendered
> empty in `current` mode, silently overwriting the complete homepage in S3
> on every push. Filtering the build traversal makes that entire failure
> class impossible — artifacts are mode-independent in content (verified:
> zero non-identical shared files between a `current` and a `full` build).

- `current` skips building one subtree: `/archive`. The list lives in
  **`databags/selective_build.yaml`** — single source of truth, also read by
  the archive workflow to derive its S3 sync scope
  (`utils/selective_build_sync_args.py`). Every entry must match an existing
  subtree under `content/`; a stale entry widens the archive deploy's sync
  scope to a prefix nothing builds.
- `archive` and `full` exclude **nothing** — a full render. Rationale: the
  current edition is only ~12% of pages, so excluding it from archive builds
  saves nothing. The difference between `archive` and `full` lives outside
  the plugin: Pagefind runs only in `full`, and the archive workflow **syncs
  only the archive scope** to S3.
- Unset (or empty) `BUILD_MODE` behaves like `full` — a plain `lektor build`
  or `make run` (dev server) builds everything, least surprise. The Makefile
  sets the mode explicitly per target, and `make run` forces the variable
  off (the dev server always prunes; a leaked `BUILD_MODE=current` would
  delete archive artifacts from the local `site/`).
- Fail fast: unknown `BUILD_MODE` value → hard error, no silent fallback.
  The config file is validated in **every** mode, so a broken
  `selective_build.yaml` fails the archive build instead of surfacing as an
  empty deploy.
- Log the active mode and the excluded paths on every build.

The pre-build generators (`redirects`, `tracks`, `topic-hubs`) always run in
every mode — they are filesystem-based, idempotent, fast, and independent of
Lektor's record discovery. Only rendering scope varies.

## Cross-edition outputs — why traversal filtering matters

Many outputs aggregate across all editions at render time: the homepage's
latest-videos section, `sitemaps/pages.xml`/`tracks.xml` and the
`*-archive.xml` segments (they walk `site.root` recursively), `/topics/`
hubs, `/llms.txt`, `/llms-full-archive.txt`. Because the plugin filters the
build traversal and **not** record discovery, all of these render complete
and **stay fresh on every production deploy** — they are ordinary
current-scope pages now. No exclusion list entry, no staleness, no risk of
an incomplete version overwriting the complete one in S3.

The one remaining special case is the **Pagefind index** (`/pagefind/`): it
indexes the built `site/` tree, which on a cold `current` build contains no
archive HTML. So `make pagefind` runs only in `full` mode, and current
deploys simply never upload a `pagefind/` dir — the last full index stays
live in S3.

Accepted consequence (decided 2026-07-02): the Pagefind index lags until the
next `full` build — current-edition talks reach `/search/` only then. No cron
backstop; run `full` manually when search freshness matters.

Sequencing note: cross-edition pages list archive URLs on every deploy, so
after importing a **new** archive edition, dispatch an `archive` build
promptly — until then the freshly listed `/archive/{year}/…` URLs 404.

## Deploy semantics

Every deploy goes through **`utils/deploy_to_s3.py`**, which syncs the built
`site/` to each bucket in `databags/deploy_targets.yaml` in turn. The sync
never passes `--delete`, so it only uploads what the build produced and never
removes bucket objects. That is what makes the whole strategy work: a
`current` deploy leaves `/archive/`, `/pagefind/` and the archive sitemap
segments untouched in the bucket.
**Invariant: never add `--delete` to the sync of a non-`full` build.**

Archive deploys sync only their scope — the excluded subtrees plus the search
index (`--exclude '*' --include archive/* --include pagefind/*`, the archive
patterns derived from `databags/selective_build.yaml`). Everything else is
already kept fresh by regular `current` deploys.

`--year 2026` narrows that further to `--include archive/2026/*`, still keeping
the search index. The **render is never narrowed**: the archive job always builds
`full`, so Pagefind always indexes the whole site. Rendering is ~106 s and the
upload is what costs minutes, so scoping the upload is both the faster and the
safer half to cut. The year is validated against the directories under
`content/archive/`, so no list needs maintaining and a typo cannot publish the
wrong subset.

**The no-delete property holds per bucket, and so does the completeness it
buys.** A bucket that never received an `archive` deploy has no archive, no
matter how many `current` deploys it has had. That is not hypothetical: when a
second bucket was added to `main.yml` alone in Aug 2026, `archive-build.yml`
kept deploying to the old one and 2,098 of the site's 2,119 sitemap URLs were
dead on the served bucket for a week, while every deploy reported success.
Naming targets in one file (`databags/deploy_targets.yaml`) rather than per
workflow is what prevents the recurrence — a new bucket needs one `archive`
or `full` dispatch before it is complete.

`site/.lektor/` (Lektor's build-state database) is excluded from every sync.

## Changes

| File | Change |
| --- | --- |
| `packages/selective-build/` | New plugin (see Mechanism); auto-loaded from `packages/` |
| `databags/selective_build.yaml` | New: the exclusion list — single source of truth for build + deploy scope |
| `utils/selective_build_sync_args.py` | New: maps the exclusion list to `aws s3 sync --include` patterns for the archive deploy |
| `Makefile` | `build` honors `BUILD_MODE` (default `current`); `pagefind` and prune only in `full`; new `build-archive`, `build-full` targets |
| `.github/workflows/main.yml` | `BUILD_MODE=current`; **`make landing-page` step removed** — landing-page is retired (decided 2026-07-02) |
| `.github/workflows/development.yml` | `BUILD_MODE=current` |
| `.github/workflows/archive-build.yml` | New: manual dispatch, input `mode` (`archive` \| `full`); `archive` syncs only the derived scope, `full` syncs everything incl. Pagefind |

Not touched: `content/archive/` stays in git as-is.

Added 2026-08-05: `databags/deploy_targets.yaml` + `utils/deploy_targets.py`
(the bucket list and its reader) and `utils/deploy_to_s3.py` (the one sync
mechanism, used by `main.yml` and `archive-build.yml`).
`.github/workflows/routing-config.yml` applies the website configuration to
every bucket in the same list.

## Attendee certificates — retired (2026-08-05)

Superseded the "certificates under the archive" question this document used to
park here. `content/attendee-certificate/` moved to `content-archived/` in
`b00f336e` and `/attendee-certificate` was dropped from
`databags/selective_build.yaml`; nothing builds or deploys them. The ~1,930
published `/attendee-certificate/{uuid}/` URLs (QR codes, shared links) are not
served. Decided deliberately, not as a side effect.

## Verification results (2026-07-02, local)

1. ✅ **Cold build timing**: `current` 22.3 s vs `full` 106.5 s (~5× faster;
   Pagefind additionally skipped in `current`).
2. ✅ **Build scope**: `current` builds exactly 603 pages; `/archive` and
   `/attendee-certificate` absent; homepage, topic hubs, `llms.txt` and all
   sitemap segments present.
3. ✅ **Cross-mode identity**: every artifact built in `current` mode is
   **byte-identical** to its `full`-mode version (zero differing shared
   files) — incl. the homepage latest-videos section (39 = 39 occurrences).
4. ✅ **Fail fast**: `BUILD_MODE=bogus` aborts the build with exit code 1.
5. ✅ **Diff test**: `BUILD_MODE=full` output byte-identical to the pre-change
   `make build` baseline (5,017 pages; only a stray `.DS_Store` differed).
6. ✅ **Lint**: ruff and markdownlint clean.
7. ✅ **Adversarial review**: 17-agent workflow, 3 lenses (Lektor internals,
   CI/CD deploy, SEO invariants), 2 independent verifiers per finding —
   5 distinct confirmed findings, all fixed (see next section).
8. ⬜ **Staging rehearsal** (remaining): deploy a `current` build to
   `pyconde-27-staging`, verify archive pages, search and sitemap segments
   still resolve from the previously synced state.
9. ⬜ **First archive dispatch** (remaining, and now urgent): `archive-build.yml`
   has never run. Dispatch it with `mode=full` — the served bucket is missing
   both `/archive/**` and `/pagefind/**`, and `full` restores both in one pass.
   Then crawl `sitemap.xml` and confirm every URL returns 200.

## Review findings & responses (2026-07-02)

1. **Homepage latest-videos rendered empty in `current` mode** (major) —
   the macro walks `site.get('/archive').children`; discovery filtering
   emptied it and every push would overwrite the complete homepage in S3.
   → Fixed structurally: filter the build traversal instead of discovery;
   all rendered pages are now mode-independent.
2. **`archive-build.yml` `full` mode could never succeed in CI** (major) —
   `pagefind` lives only in the uv dev dependency group, not
   `requirements.txt`. → Workflow installs `pagefind pagefind-bin`
   explicitly.
3. **A failing sync-args script was swallowed by `bash -e`** (major) —
   command substitution in argument position doesn't trip errexit; the
   deploy would go green having synced nothing. → Capture in a variable
   first (assignment propagates failure), and the plugin validates the
   config file in every mode so a broken list fails at build time.
4. **Mode flips on a warm build tree left stale artifacts** (minor) —
   BUILD_MODE was invisible to Lektor's dependency tracking. → Dissolved by
   the traversal-filtering rework: artifacts no longer differ by mode.
5. **`make run` with a leaked `BUILD_MODE=current` pruned archive artifacts
   from local `site/`** (minor) — the dev server always prunes. → `make run`
   forces `BUILD_MODE=` off.

## Resolved implementation questions

1. **Prune behavior**: `lektor build --no-prune` exists (Lektor 3.3.12) and is
   used for every non-`full` build, so a `current` build never deletes archive
   artifacts from a local `site/`. Only `full` prunes.
2. **Tracks & topic hubs**: the generators (`generate_redirects.py`,
   `generate_tracks.py`, `generate_topic_hubs.py`) read the **filesystem**, not
   Lektor's record tree — they are unaffected by the plugin and always run in
   every mode. Only rendering scope varies.

## Decisions (2026-07-02)

- Edition-aware directory filtering via a Lektor plugin — not build caching,
  not feature flags in git.
- Production and staging default to `current`.
- Archive/certificate rebuilds via **manual dispatch** in GitHub Actions.
- **Single `archive` mode** — per-year archive builds are not worth the
  granularity.
- **Blog is per-year** (covers only the current conference) → part of `current`.
- **Pagefind lag until the next `full` build is acceptable** — no cron backstop.
- **`landing-page` is retired** — remove its step from `main.yml`.
- Certificates are issued once per edition and effectively never change;
  updates only in rare edge cases (re-issue) — a manual archive build covers that.
- Certificate/archive git files update only when an archive build is prepared —
  acceptable.
