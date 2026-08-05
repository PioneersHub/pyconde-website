# Deployment and Hosting

The site is a static site on AWS S3. This page answers one question: **how and
when does what you see at `https://2027.pycon.de` change?**

## How and when the website is updated

**There are two update operations.**

### 1. Update the current site — automatic

Push to `main`. The workflow builds the current edition and publishes it to every
bucket. ~3 minutes. Nothing to click.

Covers everything except `/archive/**`: the homepage, the current conference's
pages, the blog, sitemaps, `llms.txt`, topic hubs.

### 2. Update the archive — on demand

Actions → **Update the archive** → Run workflow. One input, `year`:

- a year, e.g. `2026` — publishes just that edition
- `all` — publishes every edition

Use `all` after any change that affects more than one edition: a template, a
layout, a macro. Use a single year when only that edition's content changed. If
you are unsure, `all` is always correct, just slower. A year that does not exist
is rejected with the list of valid ones, so a typo cannot publish the wrong thing.

The job **always renders the whole site** and narrows only the *upload*. That is
deliberate: a year-scoped render would leave Pagefind indexing a fraction of the
site and overwrite the complete search index. Rendering costs ~2 minutes; the
upload is what costs time. The search index ships with every archive update, so
search can never silently fall behind.

### Everything else

| Trigger | Workflow | What it updates | Duration |
| --- | --- | --- | --- |
| Manual dispatch | `routing-config.yml` | The buckets' website configuration (`/latest/` alias, 404 handling) — no page content | ~30 s |
| Manual dispatch | `fetch_submissions.yml` | Pulls talks/speakers from Pretalx and **commits** them, which then triggers operation 1 | — |
| Push to `development`, or a PR to `main` | `development.yml` | The staging bucket only. Never production. | ~2.5 min |

Durations are measured from real runs on 2026-08-04. `fetch_submissions.yml` has
no recent successful run to measure; its cron is commented out between conference
cycles, so it only runs on dispatch.

### Changes that need operation 2

- **Anything under `/archive/`.** A push to `main` never rebuilds past editions.
- **A newly imported archive edition.** Cross-edition pages (homepage videos,
  sitemaps, topic hubs, `llms.txt`) list the new edition's URLs on the very next
  push — but those URLs 404 until an archive build runs. **Dispatch it promptly
  after importing an edition.**
- **Sponsor pages.** `make sponsor-pages` is disabled in both deploy workflows;
  run it locally and commit the result.
- **Redirect rules and 404 behaviour.** `databags/routing.yaml` changes are
  inert until `routing-config.yml` is dispatched.

Talk permalinks are **not** in this list — they refresh on every deploy. See
[Talk permalinks](#talk-permalinks--talkspretalx_code) below.

### Deleting never happens automatically

The sync **never** passes `--delete`. Removing a page from `content/` and
pushing does **not** remove it from the site — the old object stays in the
bucket and keeps being served. To take a page down you must delete the object
yourself:

```bash
aws s3 rm "s3://<bucket>/<path>/index.html"
```

This is not an oversight. It is what lets a current-edition build deploy ~12% of
the site without wiping the other 88%. See `plans/selective-builds.md`.

## Build scope — why a push only updates part of the site

`make build` takes a `BUILD_MODE`:

| Mode | Renders | Used by |
| --- | --- | --- |
| `current` | Current edition only (~600 pages) | `main.yml`, `development.yml` |
| `archive` | Everything | nothing in CI; available locally |
| `full` | Everything, plus the Pagefind index | `archive-build.yml`, local `make build` |

A cold `full` render is ~5× slower than `current` and re-indexes ~486 MB, and
88% of that work reproduces pages that have not changed since they were
archived. Hence the split. The excluded subtree list lives in
`databags/selective_build.yaml` and drives both build scope and deploy scope.

Note that build scope and *upload* scope are separate knobs. The archive job
always builds `full` and narrows the upload with `--year`; see
`utils/deploy_to_s3.py`.

## Talk permalinks — `/talks/{PRETALX_CODE}/`

A talk's URL moves during its life: `/talks/{slug}/` while its conference is the
current edition, `/archive/{YYYY}/talks/{slug}/` once the edition is archived.
`/talks/{PRETALX_CODE}/` is the URL that never moves — the one to print on a
badge, put in slides, or cite.

```text
/talks/BFL7MQ/  →  301  →  /archive/2026/talks/from-scratch-to-scale-…/
```

**Nobody maintains these.** Both deploy workflows run `utils/talk_permalinks.py`
on every deploy, and it reconciles rather than only writing:

| Event | What happens by itself |
| --- | --- |
| A talk is imported from Pretalx | its permalink appears on the same push that publishes the page |
| A talk's title changes, so its slug changes | the permalink is repointed |
| An edition is archived | every affected permalink follows the talk to `/archive/{YYYY}/` |
| A talk is withdrawn | its permalink is deleted, rather than left redirecting into a 404 |
| Two talks share a code | the deploy **fails**, naming both records — an ambiguous permalink never ships |

Inspect the mapping locally with `make talk-permalinks` (prints, writes nothing).

Implementation notes worth knowing before changing anything:

- They are **S3 object metadata** (`x-amz-website-redirect-location`), not pages
  in `site/`. So they do not exist locally or on staging, and `make serve` cannot
  reproduce them. They only work on the bucket's *website* endpoint, which is
  what nginx uses.
- The bucket website configuration cannot do this job: S3 allows **50 routing
  rules** and there are ~850 talks.
- Only six-character uppercase Pretalx codes get a permalink. The 2016 and 2017
  talks predate Pretalx and carry a slug in their `code:` field; giving those a
  permalink would collide with a real page at `/talks/{slug}/` the moment a
  future edition produced the same slug.

## Where the site lives

**`databags/deploy_targets.yaml` is the only place buckets are named.** Every
workflow that uploads or configures reads it through `utils/deploy_targets.py`.
No workflow may name a bucket itself.

That rule exists because the alternative failed. When the site moved to a new
bucket, only `main.yml` was pointed at it; `archive-build.yml` and
`routing-config.yml` kept deploying to the old one. For a week, 2,098 of the
site's 2,119 sitemap URLs were dead on the served bucket while every deploy
reported success.

A list entry is either a literal bucket name or `env:VARNAME`, resolved at run
time from the GitHub secret of the same name — this repo is public, so a name
that should not be published goes in a secret and is referenced by variable. An
unresolvable entry is a hard error, never a quietly shorter list.

**Each bucket gets a complete, independent copy.** Whichever bucket is live must
serve the whole site on its own; there is no fallback between them. A bucket
added to the list is **not complete** until it has received one
`archive-build.yml` dispatch, because `main.yml` only ever uploads the current
edition.

**Which bucket is live is decided by nginx, outside this repository.** Nothing
in the repo, and no green Actions run, tells you which one that is. Check the
server config before assuming a deploy reached visitors — see
[docs/hosting-proxy.md](hosting-proxy.md), which also covers the apex redirect
and the still-live per-year sites.

## Running a workflow

GitHub → **Actions** → pick the workflow in the left sidebar → **Run workflow**
(top right of the run list) → choose the branch → set inputs → **Run workflow**.

Or from a terminal:

```bash
gh workflow run archive-build.yml --ref main -f mode=full
gh run watch
```

### routing-config.yml — always dry-run first

`aws s3api put-bucket-website` **replaces the entire configuration in one call**
and AWS keeps no history. There is no undo.

1. Dispatch with `dry_run` **true** (the default). It prints each bucket's
   current configuration and the configuration it would apply, then stops.
2. **Save that log** — `gh run view --log > routing-before.txt`. It is the only
   copy of the pre-change state.
3. Confirm: one `::group::` per bucket; the generated config shows
   `ErrorDocument: 404.html` and the expected `/latest/` rule.
4. Re-dispatch with `dry_run` **false**.

Run it **after** the content is in place, never before. It removes any catch-all
404 fallback, so URLs still missing from the bucket stop redirecting to the
homepage and start returning real 404s. The `/latest/` rule also points into
`/archive/{year}/`, which must exist by then.

The loop is not atomic: if the second bucket fails, the first already has the
new configuration. Re-running fixes it — the operation is idempotent.

## Verifying an update reached visitors

A green Actions run only proves the upload succeeded. To prove the *site*
changed, ask the site:

```bash
curl -sI https://2027.pycon.de/some/page/ | head -1        # 200
```

Full check, after an archive build — every URL the site advertises:

```bash
BASE=https://2027.pycon.de
curl -sS "$BASE/sitemap.xml" | grep -oE '<loc>[^<]+</loc>' | sed -E 's|</?loc>||g' > sitemaps.txt
: > urls.txt
while read -r sm; do
  curl -sS "$sm" | grep -oE '<loc>[^<]+</loc>' | sed -E 's|</?loc>||g' >> urls.txt
done < sitemaps.txt
sort -u urls.txt | grep "^$BASE/" > clean.txt

xargs -P 25 -n1 -I{} sh -c 'printf "%s %s\n" "$(curl -sS -o /dev/null -w "%{http_code}" --max-time 25 "{}")" "{}"' \
  < clean.txt > results.txt
awk '{print $1}' results.txt | sort | uniq -c     # expect: all 200
awk '$1!=200' results.txt                          # expect: empty
```

Run this before dispatching `routing-config.yml`. Afterwards there is no
catch-all to hide a missing page.

## Emergency deploy from a laptop

Prefer the workflows. If you must, use the same script CI uses — a bare
`aws s3 cp` writes to one bucket and silently skips the other:

```bash
make build BUILD_MODE=full
python utils/deploy_to_s3.py --scope full        # add --dry-run to preview
```

## Secrets and permissions

| Secret | Used for |
| --- | --- |
| `AWS_S3_BUCKET` | The legacy bucket, referenced as `env:AWS_S3_BUCKET` from `databags/deploy_targets.yaml`. Delete the secret and the list entry together when the migration ends. |
| `AWS_S3_REGION` | Note the name — `AWS_REGION` is **not** read by any workflow. |
| `AWS_ACCESS_KEY_ID` | |
| `AWS_SECRET_ACCESS_KEY` | |

The IAM principal needs `s3:PutObject` and `s3:ListBucket` on **every** bucket
in the list, plus `s3:GetBucketWebsite` and `s3:PutBucketWebsite` for
`routing-config.yml`. A policy scoped to one bucket's ARN fails in the way that
hurts most: the other bucket simply never updates, and nothing goes red.

## Reference: creating a bucket from scratch

Region `eu-central-1`. Needs the AWS CLI and credentials that can create and
configure buckets.

```bash
aws s3api create-bucket --bucket <bucket-name> --region eu-central-1 \
  --create-bucket-configuration LocationConstraint=eu-central-1

aws s3api put-public-access-block --bucket <bucket-name> \
  --public-access-block-configuration "BlockPublicPolicy=false"

aws s3api put-bucket-policy --bucket <bucket-name> --policy '{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::<bucket-name>/*"]
        }
    ]
}'

aws s3 website "s3://<bucket-name>" --index-document index.html
```

Then add it to `databags/deploy_targets.yaml`, push (which fills it with the
current edition), dispatch `archive-build.yml` with `mode=full` (which makes it
complete), and dispatch `routing-config.yml` (which gives it the redirect rules
and the 404 page). Verify with the sitemap crawl above **before** pointing nginx
at it.

For SSL and custom domain setup, see the bucket's properties page in the AWS
console.
