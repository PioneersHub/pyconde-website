# Cloudflare Deployment Playbook

Publish the site from Cloudflare **without changing `pycon.de` nameservers**. The zone stays at
fcio.net; the only DNS change is one CNAME record per hostname we want to serve.

First step: `new.pycon.de` published from a local machine, alongside the existing S3 production
site, changing nothing about the current deploy. Then GitHub Actions. The same setup carries any
further subdomain — see [§6](#6-what-the-no-nameserver-change-constraint-costs) for the one thing
it cannot do.

This playbook is written to be executed top to bottom. Every phase ends with a verification step;
do not start the next phase until the previous one verifies.

## 1. Facts this plan is built on

Checked on 2026-08-04 against the repository and live DNS. Re-check before executing if
significant time has passed.

| Fact | Value | Consequence |
| --- | --- | --- |
| `pycon.de` nameservers | `ns3.fcio.net`, `ns4.fcio.net` | Stays that way. Determines the platform — see [§2](#2-platform-choice). |
| `pycon.de` A record | `185.105.252.28` | Untouched. |
| `2027.pycon.de` | CNAME → `pysv02.fe.rzob.gocept.net.` | Current production host. Untouched. |
| Built site file count | 8,894 files (`site/`, excluding `site/.lektor/`) | Under the 20,000-file free-plan cap, comfortably under the 100,000 paid cap. |
| Built site size | ~370 MB (plus a 224 MB `site/.lektor/` build-state directory) | `site/.lektor/` **must** be excluded from upload. |
| Largest deployable file | `site/static/mediakit/PyConDE PyData 2026 Media Kit 2026-03.zip`, 33 MB | **Blocker.** Exceeds Cloudflare's 25 MiB per-asset limit. See [3.4](#34-the-33-mb-media-kit). |
| Prefix redirects needed | 1 (`/latest/` → `/archive/2026/`, from `databags/routing.yaml`) | Trivially within the 2,000-static-redirect `_redirects` limit. |
| Per-talk and manual redirects | Rendered as HTML meta-refresh pages by Lektor | Already part of `site/`. No hosting config needed. |
| Contact form backend | FastAPI on AWS Lambda (`backend/`) | Out of scope. Stays on AWS. Only CORS/CSP needs a look when the origin host changes. |

Cloudflare limits used below, from the current docs:

- Static assets: **20,000 files** (free) / **100,000 files** (paid), **25 MiB** maximum per file.
- `_redirects`: **2,000 static + 100 dynamic** rules, 1,000 characters per line.
- `_headers`: **100 rules**.

## 2. Platform choice

**Cloudflare Pages.** It is the only Cloudflare product that serves a custom domain on a zone
whose nameservers are elsewhere: you register the hostname with the Pages project, then CNAME it
to `<project>.pages.dev` at fcio.net. Cloudflare issues the certificate by domain validation.

Workers Static Assets is not an option here and is not mentioned again: Workers custom domains
require Cloudflare-managed nameservers. Same for a Cloudflare "subdomain zone" for `new.pycon.de`
(delegating that one label by NS record) — Enterprise-only, and still a nameserver change.

Static asset requests on Pages are free and unmetered. The cost question is only the file-count
tier: 20,000 files free, 100,000 on Pages Pro ($20/mo). At 8,894 files today and roughly
1,000–1,500 added per edition, the free tier holds for several more cycles.

## Phase 0 — Prerequisites

Confirm before starting. Any missing item stops the phase; do not work around it.

1. **Cloudflare account with access to create Pages projects.** Note the account ID:

   ```bash
   npx wrangler@latest login
   npx wrangler@latest whoami
   ```

   `whoami` prints the account name and ID. Record the ID; Phase 4 needs it.

2. **Write access to `pycon.de` DNS at fcio.net.** Phase 2 adds one CNAME record. Nothing else in
   the zone is touched — no nameserver change, no MX change, nothing that can affect mail.

3. **Node.js.** Present locally (v26.5.1). Wrangler is invoked via `npx`; do not add it to
   `package.json` — this repo has no JavaScript toolchain and should not grow one for a CLI.

4. **A local build that succeeds:**

   ```bash
   make build BUILD_MODE=full
   ```

   `full` is required: `current` skips `/archive` and `/attendee-certificate` entirely, and a
   Pages deployment is an immutable snapshot — there is no previous deploy for those pages to
   survive in, the way they persist in the S3 bucket between archive syncs. See the
   [Phase 4 note](#build-mode-under-pages).

   Verify: `find site -type f ! -path 'site/.lektor/*' | wc -l` returns a number in the
   8,000–10,000 range.

## Phase 1 — Smoke test on `*.pages.dev`

No DNS change at all. This proves the artifact uploads and serves correctly before any `pycon.de`
hostname points at it.

1. Apply the [Phase 3](#phase-3--repository-changes) repository changes first — specifically
   `site/.assetsignore`, without which the upload includes 224 MB of Lektor build state and fails
   on the 33 MB media kit zip. Phase 3 is listed after this one because it is repo work rather
   than Cloudflare work, but it is a prerequisite here.

2. Create the project (direct upload, no Git connection):

   ```bash
   npx wrangler@latest pages project create pyconde-website --production-branch main
   ```

3. Deploy:

   ```bash
   npx wrangler@latest pages deploy site \
     --project-name=pyconde-website \
     --branch=main \
     --commit-dirty=true
   ```

   The first upload moves ~337 MB and takes several minutes. Later deploys upload only files whose
   hashes changed.

4. **Verify — do not skip:**

   - Wrangler's output reports an uploaded file count. It must be close to 8,894 and must **not**
     be in the tens of thousands. A count above ~10,000 means `.assetsignore` was not picked up
     and `site/.lektor/` went along; stop and fix it.
   - Open the printed `https://<hash>.pyconde-website.pages.dev` URL.
   - Spot-check search (`/search`) — Pagefind loads its index over fetch and is the most likely
     thing to break on a new origin.
   - Spot-check one attendee certificate page and one talk page under `/archive/2026/talks/`.
   - Check the routing surface:

   ```bash
   BASE=https://pyconde-website.pages.dev
   curl -sI "$BASE/" | head -1                      # 200
   curl -sI "$BASE/imprint" | head -1               # 301 → /imprint/
   curl -sI "$BASE/imprint/" | head -1              # 200
   curl -sI "$BASE/latest/" | head -1               # 301 → /archive/2026/
   curl -sI "$BASE/no-such-page/" | head -1         # 404, body is the styled 404 page
   curl -sI "$BASE/archive/2026/" | head -1         # 200
   curl -s  "$BASE/robots.txt" | head -3
   ```

## Phase 2 — Point `new.pycon.de` at it

**Order matters.** Register the domain with the Pages project *before* creating the DNS record. A
CNAME that resolves to `pages.dev` for a hostname the project does not know returns HTTP 522.

1. In the Cloudflare dashboard: **Workers & Pages → pyconde-website → Custom domains → Set up a
   domain**, enter `new.pycon.de`. Cloudflare shows the CNAME target and begins certificate
   issuance.

   Equivalent API call, if you prefer scripting it:

   ```bash
   curl -X POST \
     "https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/pages/projects/pyconde-website/domains" \
     -H "Authorization: Bearer ${CF_API_TOKEN}" \
     -H "Content-Type: application/json" \
     --data '{"name":"new.pycon.de"}'
   ```

2. At fcio.net, add exactly one record:

   ```
   new.pycon.de.   CNAME   pyconde-website.pages.dev.
   ```

   Use a short TTL (300s) for the first days so a rollback propagates quickly.

3. Wait for the dashboard to report the domain **Active** — this is certificate issuance via
   domain validation and typically takes minutes, occasionally longer.

4. **Verify:**

   ```bash
   dig +short new.pycon.de
   curl -sI https://new.pycon.de/ | head -5
   curl -sI https://new.pycon.de/latest/ | head -3
   curl -sI https://new.pycon.de/ | grep -i x-robots-tag   # expect: noindex, nofollow
   ```

   Then re-run the Phase 1 URL checks against `https://new.pycon.de`.

5. **Rollback:** delete the CNAME at fcio.net. Nothing else is affected — production
   (`pycon.de`, `2027.pycon.de`, S3, mail) was never in the path.

### Keeping `new.pycon.de` out of search results

The site's canonical tags already point at `https://2027.pycon.de`, which limits the damage, but
that is not a guarantee. Phase 3 generates a `_headers` file that sets
`X-Robots-Tag: noindex, nofollow` on every response, emitted only for staging builds. Verify the
header is present (step 4 above) before sharing the URL.

## Phase 3 — Repository changes

Four changes, all small. They are additive: the S3 deploy path is untouched and keeps working.

### 3.1 `site/.assetsignore`

Cloudflare reads `.assetsignore` (gitignore syntax) from the root of the asset directory and skips
matching files. Required contents:

```
.assetsignore
.lektor/
static/mediakit/*.zip
```

`site/` is gitignored and regenerated, so this file must be **written by the build**, not
committed.

### 3.2 `site/_redirects`

Generated from `databags/routing.yaml` — the same source that already produces the S3 website
configuration — so the `/latest/` rule is never written twice. Extend
`utils/generate_routing_config.py` with an output mode that renders the rules already returned by
its `load_rules()` into Cloudflare's format, rather than adding a second script with its own copy
of the rules:

```
# generated from databags/routing.yaml
/latest/* /archive/2026/:splat 301
```

Plus one hand-maintained line for the oversized media kit (see 3.4), pointing at a host that can
serve a 33 MB file:

```
/static/mediakit/PyConDE%20PyData%202026%20Media%20Kit%202026-03.zip https://<current-production-host>/static/mediakit/PyConDE%20PyData%202026%20Media%20Kit%202026-03.zip 302
```

Use the exact encoded path, not a `/static/mediakit/*` splat — a splat would also capture the
1.7 MB brand manual PDF, which *is* uploaded and should be served locally. Redirects are evaluated
before assets are served, so a too-broad rule silently shadows a working file.

### 3.3 `site/_headers` (staging builds only)

```
/*
  X-Robots-Tag: noindex, nofollow
```

Emit this only when the build targets `new.pycon.de`. A build variable alongside the existing
`BUILD_MODE` is the natural fit — for example `DEPLOY_TARGET=staging`, defaulting to unset so
production builds never carry the header. Do not make "production" the fallback for an unset or
misspelled value; an unrecognised target should fail the build rather than silently ship a
`noindex` to production, or silently drop it from staging.

### 3.4 The 33 MB media kit

`site/static/mediakit/PyConDE PyData 2026 Media Kit 2026-03.zip` is 33 MB against a hard 25 MiB
per-asset limit. It cannot be uploaded to Pages as-is. Options:

1. **Redirect to the existing host** (3.2 above). Zero new infrastructure, the link in
   `content/media-kit/contents.lr:11` keeps working, and it is reversible. Correct choice while S3
   is still live.
2. **R2 behind a Pages Function.** Put the zip in an R2 bucket, bind the bucket to the Pages
   project, and stream it from a Function at `/static/mediakit/*`. This is the only way to serve
   the file from Cloudflare without a nameserver change — an R2 custom hostname
   (`assets.pycon.de`) would need the zone on Cloudflare, and the `pub-*.r2.dev` URL is
   rate-limited and explicitly not for production. Costs a Function invocation per download and
   introduces the repo's first piece of edge code.
3. **Split or recompress below 25 MiB.** Changes a published artifact and its documented size.
   Cheapest if the media kit is being revised anyway.

Option 1 now. Option 3 is the better permanent answer if the file is ever regenerated; option 2 is
the fallback if S3 goes away first. Whichever you pick, **the S3 bucket cannot be decommissioned
until this file has another home** — track it.

### 3.5 Makefile wiring

Add a target that writes `.assetsignore`, `_redirects` and `_headers` into `site/`, and hang it off
`build` **after** `lektor-build`. Lektor's prune only deletes artifacts recorded in its own build
state (`lektor/builder.py`, `iter_artifacts` / `prune`) — it does not sweep unknown files out of
the output directory, which is why the existing `pagefind` step can already write into `site/`.
Ordering it last is for clarity, not safety.

Verification for this phase: after `make build`, all three files exist in `site/`, and
`grep -c '' site/_redirects` shows the expected rule count.

## Phase 4 — GitHub Actions

Only after Phase 2 verifies and the site has been reviewed on `new.pycon.de`.

Add a workflow that mirrors the existing `development.yml` but targets Pages. Keep it on
`workflow_dispatch` at first so the S3 production deploy stays the sole `main` consumer until you
are ready to cut over.

```yaml
name: Deploy to Cloudflare Pages

on:
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      deployments: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version-file: '.python-version'
          cache: 'pip'
      - run: pip install -r requirements.txt pagefind pagefind-bin
      - run: make build BUILD_MODE=full DEPLOY_TARGET=staging
      - uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: pages deploy site --project-name=pyconde-website --branch=main
```

Secrets to add to the repository:

- `CLOUDFLARE_API_TOKEN` — scoped to **Account → Cloudflare Pages → Edit**, nothing more.
- `CLOUDFLARE_ACCOUNT_ID` — from `wrangler whoami` in Phase 0.

`pagefind` and `pagefind-bin` are installed explicitly because they live in the dev dependency
group, which the compiled `requirements.txt` omits — the same reason `archive-build.yml` installs
them for its `full` mode.

### Build mode under Pages

**This is the one part of the S3 setup that does not translate.** `BUILD_MODE=current` works today
because the S3 sync layers a partial build onto a bucket that still holds the archive from the
last `archive-build.yml` run. A Pages deployment is an immutable snapshot: a `current`-only build
would publish a site with **no archive and no certificates at all**, not a site that inherits them.

So on Pages, every deploy must be `BUILD_MODE=full`. That is slower — it renders every past
edition and rebuilds the Pagefind index on each run — but it is correct, and it is the only option
that does not require restructuring. Measure a full CI build before making Pages production; if
the runtime is unacceptable, the alternative is to move `/archive` out of the deployment snapshot
(option 2 in [3.4](#34-the-33-mb-media-kit) generalised), which is a much larger piece of work.

Either way, `plans/selective-builds.md` needs a note that its `current`/`archive` split is
S3-specific.

## Phase 5 — Making it production

When `new.pycon.de` has run in parallel long enough to trust it:

1. Register the production hostname with the same Pages project and CNAME it at fcio.net, exactly
   as in Phase 2. `www.pycon.de` and `2027.pycon.de` both work this way.
2. Drop `DEPLOY_TARGET=staging` from the workflow for the production deploy so the `noindex`
   header is not emitted. If both hostnames are served from one project they share one deployment
   and therefore one `_headers` file — so pick one: either `new.pycon.de` stops being `noindex`,
   or production gets its own Pages project. A second project is the cleaner answer and costs
   nothing.
3. Change the workflow trigger from `workflow_dispatch` to `push: branches: [main]`, and retire
   the S3 deploy in `main.yml` only once Cloudflare has served a full conference cycle.
4. Keep `canonical_host` in `databags/branding.yaml` and `url` in `PyconDE.lektorproject` in sync
   with whatever hostname actually serves the site.

## 6. What the no-nameserver-change constraint costs

Exactly one thing: **the apex `pycon.de` cannot be served by Pages.** Cloudflare requires a custom
apex domain to be a zone on the Cloudflare account; that is a Pages-side rule, so no DNS trick at
fcio (ALIAS, ANAME, flattening) works around it. Subdomains are unaffected.

Practical consequence: the real site lives at `www.pycon.de` (or another subdomain), and the apex
keeps a 301 to it from wherever it is hosted today. That is a standard arrangement and costs
nothing in SEO as long as the redirect is a permanent one and canonical tags point at the
subdomain.

If serving the bare `pycon.de` from Cloudflare ever becomes a requirement, it means moving the
zone — a separate decision with its own risk profile, chiefly the `info26@pycon.de` mail records.
Nothing in this playbook forecloses it.

## Open decisions

1. **Media kit long-term home** — [3.4](#34-the-33-mb-media-kit). Redirect now; decide between
   recompressing and R2 before S3 is retired.
2. **Full-build runtime in CI** — measure it before Phase 5, see [Build mode under Pages](#build-mode-under-pages).
3. **One Pages project or two** (staging + production) — [Phase 5](#phase-5--making-it-production)
   step 2. Two is cleaner and free.
4. **Which hostname becomes production** — `www.pycon.de` is the obvious candidate given the apex
   constraint.

## See also

- `docs/deployment.md` — the current S3 setup, still authoritative for production.
- `docs/redirects.md` — the three redirect layers and why only one needs hosting config.
- `plans/selective-builds.md` — the `BUILD_MODE` split, which is S3-specific.
- [Pages custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/) ·
  [Pages limits](https://developers.cloudflare.com/pages/platform/limits/) ·
  [`_redirects`](https://developers.cloudflare.com/pages/configuration/redirects/) ·
  [`_headers`](https://developers.cloudflare.com/pages/configuration/headers/) ·
  [Direct upload from CI](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/)
