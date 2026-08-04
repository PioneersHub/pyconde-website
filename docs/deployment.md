# Deployment and Hosting

The site is hosted as a static site on AWS/S3.

## Where the site is deployed

**`databags/deploy_targets.yaml` is the only place buckets are named.** Every
workflow that uploads the site or configures a bucket reads it through
`utils/deploy_targets.py`. No workflow may name a bucket itself.

That rule exists because the alternative failed. When the site moved to a new
bucket, only `main.yml` was updated; `archive-build.yml` and
`routing-config.yml` kept targeting the old one. For a week 2,098 of the site's
2,119 sitemap URLs were dead on the served bucket while every deploy reported
success.

An entry is either a literal bucket name or `env:VARNAME`, resolved at run time
from the GitHub secret of the same name — this repository is public, so a name
that should not be published goes in a secret and is referenced by variable. An
unresolvable entry is a hard error, never a skipped bucket.

**Each bucket gets a complete, independent copy.** There is no runtime
dependency between them: whichever bucket is live must be able to serve the
whole site on its own. A bucket added to the list is *not* complete until it has
received one `archive-build.yml` dispatch — `main.yml` only ever uploads the
current edition.

**Which bucket is actually live is decided by nginx, outside this repository.**
Nothing in the repo or in a green Actions run tells you which one that is. Check
the server config before assuming a deploy reached visitors.

## Deploying

```bash
make build BUILD_MODE=full          # or BUILD_MODE=current
python utils/deploy_to_s3.py --scope full
```

`--scope` selects which slice of `site/` to upload (`full` or `archive`), not
what was built. `--dry-run` prints the resolved buckets and the exact `aws`
command without uploading and without needing credentials. The sync **never**
passes `--delete` — see `plans/selective-builds.md`.

Prefer the workflows; see Automated Deployment below.

To (re-)create the S3 bucket setup in the eu-central-1 region, run the following:

Prerequisites:

- AWS CLI
- AWS credentials with permissions to create and manage S3 buckets

Create the bucket:

```bash
aws s3api create-bucket --bucket <bucket-name> --region eu-central-1 --create-bucket-configuration LocationConstraint=eu-central-1
```

Configure public access settings:

```bash
aws s3api put-public-access-block --bucket <bucket-name> --public-access-block-configuration "BlockPublicPolicy=false"
```

Verify the configuration:

```bash
aws s3api get-bucket-ownership-controls --bucket <bucket-name>
```

Apply public read policy:

```bash
aws s3api put-bucket-policy --bucket <bucket-name> --policy '{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": [
                "arn:aws:s3:::'<bucket-name>'/*"
 
            ]
        }
    ]
}'
```

Deploy website to S3:

```bash
aws s3 cp site/ s3://<bucket-name>/ --recursive
```

Configure website index document:

```bash
aws s3 website s3://<bucket-name> --index-document index.html
```

Verify deployment:

```bash
curl <bucket-name>.s3-website.eu-central-1.amazonaws.com
```

For SSL and custom domain setup, see the AWS S3 bucket properties page:
https://eu-central-1.console.aws.amazon.com/s3/buckets/<bucket-name>?region=eu-central-1&bucketType=general&tab=properties

## Automated Deployment

Three workflows write to the buckets in `databags/deploy_targets.yaml`:

| Workflow | Trigger | What it deploys |
| --- | --- | --- |
| `main.yml` | push to `main`, dispatch | Current edition (`BUILD_MODE=current`) |
| `archive-build.yml` | dispatch | `mode=archive`: `/archive/**`. `mode=full`: everything, incl. the Pagefind search index |
| `routing-config.yml` | dispatch | The bucket website configuration from `databags/routing.yaml` |

A new bucket needs one `archive-build.yml` dispatch with `mode=full` before it
serves a complete site. `routing-config.yml` should be run **last**: it removes
any catch-all fallback, so URLs that were soft-redirecting to the homepage start
returning real 404s.

Required GitHub secrets:

- `AWS_S3_BUCKET` — the legacy bucket, referenced as `env:AWS_S3_BUCKET` from
  `databags/deploy_targets.yaml`. Delete both when the migration is signed off.
- `AWS_S3_REGION` — note the name: `AWS_REGION` is not read by any workflow.
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

The IAM principal needs `s3:PutObject` and `s3:ListBucket` on **every** bucket
in the list, plus `s3:GetBucketWebsite` and `s3:PutBucketWebsite` for
`routing-config.yml`. A policy scoped to one bucket's ARN fails silently in the
sense that matters: the other bucket simply never updates.

## Manual Deployment

Use GitHub Actions for deployment to maintain consistency. Manual deployment
risks creating discrepancies — in particular it is easy to deploy to one bucket
and forget the other, which is exactly what `utils/deploy_to_s3.py` exists to
prevent. For emergency deployments, use it rather than a bare `aws s3` command:

```bash
make build BUILD_MODE=full
python utils/deploy_to_s3.py --scope full
```
