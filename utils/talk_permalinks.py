"""Manage the /talks/{PRETALX_CODE}/ permalinks as S3 object redirects.

A talk's URL moves during its life: it sits at /talks/{slug}/ while its
conference is the current edition, then at /archive/{YYYY}/talks/{slug}/
once the edition is archived. /talks/{CODE}/ is the URL that never moves —
the one to print, share and cite.

Each permalink is a zero-byte S3 object carrying
`x-amz-website-redirect-location`, which the bucket's *website* endpoint
serves as a real HTTP 301. The bucket website configuration cannot do this
job: S3 allows at most 50 routing rules and there are ~850 talks.

Nobody has to maintain these. Both deploy workflows run this script on every
deploy, and it RECONCILES rather than only writing: codes gain permalinks,
moved talks get repointed, and withdrawn talks have their permalink deleted
instead of left redirecting into a 404 (the sync never deletes, so nothing
else would ever clean them up).

    python utils/talk_permalinks.py --dry-run   # print the plan, touch nothing
    python utils/talk_permalinks.py             # reconcile every bucket

Credentials come from the usual AWS_* environment variables. Buckets come
from databags/deploy_targets.yaml via utils/deploy_targets.py.
"""

from __future__ import annotations

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
from botocore.config import Config
from deploy_targets import resolve_targets

REPO = Path(__file__).resolve().parent.parent
CONTENT = REPO / "content"
SITE = REPO / "site"

# Pretalx codes are exactly six uppercase alphanumerics. Talks imported before
# Pretalx (2016-2017) carry their slug in the `code:` field instead; those are
# deliberately NOT given a permalink. A lowercase slug-shaped permalink would
# collide with a real current-edition page at /talks/{slug}/ the moment some
# future edition produced the same slug — "conference-opening" and friends
# recur every year.
PRETALX_CODE = re.compile(r"^[A-Z0-9]{6}$")

# The same shape, as an S3 key. Reconciliation deletes only keys matching this,
# so it can never touch a real talk page (those are lowercase).
# The S3 folder the permalinks live in. Named so utils/deploy_to_s3.py can
# refuse to mirror (delete-sync) it: the redirects are not in site/.
PERMALINK_ROOT = "talks"
PERMALINK_KEY = re.compile(r"^talks/[A-Z0-9]{6}/index\.html$")

CODE_FIELD = re.compile(r"^code:\s*(\S+)\s*$", re.M)

MAX_WORKERS = 16

# How many offending entries an error message lists before truncating.
MAX_REPORTED = 10


def talk_permalinks() -> dict[str, str]:
    """Map Pretalx code -> the URL path that talk currently builds to.

    Derived from where each record actually sits in the tree, so the
    current-edition and archived cases need no separate handling: moving a
    talk folder is all it takes for the next run to repoint its permalink.
    """
    mapping: dict[str, str] = {}
    seen: dict[str, Path] = {}

    for contents in sorted(CONTENT.rglob("talks/*/contents.lr")):
        text = contents.read_text(encoding="utf-8", errors="replace")
        if "_model: redirect" in text:
            continue  # the existing per-year code stubs, not talks
        match = CODE_FIELD.search(text)
        if not match:
            continue
        code = match.group(1)
        if not PRETALX_CODE.match(code):
            continue

        folder = contents.parent
        if code in seen:
            raise SystemExit(
                f"Duplicate Pretalx code {code!r}:\n"
                f"  {seen[code].relative_to(REPO)}\n"
                f"  {folder.relative_to(REPO)}\n"
                f"A permalink cannot point at two talks. Fix the code: field in one."
            )
        seen[code] = folder

        # content/talks/{slug}/            -> /talks/{slug}/
        # content/archive/{yy}/talks/{slug}/ -> /archive/{yy}/talks/{slug}/
        mapping[code] = "/" + str(folder.relative_to(CONTENT)).replace("\\", "/") + "/"

    if not mapping:
        raise SystemExit(
            f"No Pretalx-coded talks found under {CONTENT}. Refusing to reconcile: "
            f"this would delete every existing permalink."
        )
    return mapping


def assert_targets_built(mapping: dict[str, str]) -> None:
    """Fail if a permalink points at a page the build should have produced.

    A permalink into a 404 is worse than no permalink, so every target is
    checked against site/ — but only where checking means anything.

    Builds are scoped: BUILD_MODE=current renders no /archive at all (see
    databags/selective_build.yaml), and that is exactly what main.yml runs.
    Those pages are already deployed and the sync never deletes, so their
    permalinks stay valid; they simply cannot be verified from this build.
    A target is therefore skipped when its whole top-level section is absent
    from site/, and failed when the section is present but the page is not —
    which is real breakage. Skips are reported, never silent.
    """
    missing: list[str] = []
    unbuildable: set[str] = set()

    for code, url in sorted(mapping.items()):
        path = url.strip("/")
        if (SITE / path / "index.html").is_file():
            continue
        section = path.split("/", 1)[0]
        if not (SITE / section).is_dir():
            unbuildable.add(section)  # out of this build's scope
        else:
            missing.append(f"{code} -> {url}")

    if unbuildable:
        print(
            f"note: /{'/, /'.join(sorted(unbuildable))} not in this build "
            f"(BUILD_MODE=current renders no archive) — those permalinks are "
            f"written from the mapping without a local target check.",
            file=sys.stderr,
        )

    if missing:
        raise SystemExit(
            f"{len(missing)} permalink target(s) missing from a section that WAS built:\n  "
            + "\n  ".join(missing[:MAX_REPORTED])
            + ("\n  ..." if len(missing) > MAX_REPORTED else "")
            + "\nRun `make build BUILD_MODE=full` first, or fix the talk records."
        )


def s3_client():
    """One client shared by the worker threads; boto3 clients are thread-safe.

    In-process calls, not one `aws` CLI process per object: starting ~1,700
    of those (every permalink, every bucket) was most of a deploy's runtime.
    The connection pool matches the thread pool so no worker waits on another.
    """
    return boto3.client("s3", config=Config(max_pool_connections=MAX_WORKERS))


def existing_permalinks(s3, bucket: str) -> set[str]:
    pages = s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=f"{PERMALINK_ROOT}/"
    )
    return {
        obj["Key"]
        for page in pages
        for obj in page.get("Contents", [])
        if PERMALINK_KEY.match(obj["Key"])
    }


def put_permalink(s3, bucket: str, code: str, target: str) -> None:
    s3.put_object(
        Bucket=bucket,
        Key=f"talks/{code}/index.html",
        WebsiteRedirectLocation=target,
        Body=b"",
    )


def delete_permalink(s3, bucket: str, key: str) -> None:
    s3.delete_object(Bucket=bucket, Key=key)


def reconcile(s3, bucket: str, mapping: dict[str, str]) -> None:
    """Make the bucket's permalinks match the mapping exactly.

    Every permalink is rewritten, not only the ones that look changed:
    listing does not return the redirect target, so finding the changed ones
    would cost one request per key anyway, and rewriting is idempotent.
    """
    wanted = {f"talks/{code}/index.html" for code in mapping}
    stale = sorted(existing_permalinks(s3, bucket) - wanted)

    print(f"::group::permalinks -> s3://{bucket}", flush=True)
    print(f"  {len(mapping)} permalinks, {len(stale)} stale", flush=True)
    for key in stale:
        print(f"  delete {key}", flush=True)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        list(
            pool.map(
                lambda kv: put_permalink(s3, bucket, kv[0], kv[1]), mapping.items()
            )
        )
        list(pool.map(lambda key: delete_permalink(s3, bucket, key), stale))

    print("::endgroup::", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the mapping and the resolved buckets without calling AWS.",
    )
    args = parser.parse_args()

    mapping = talk_permalinks()
    assert_targets_built(mapping)

    if args.dry_run:
        for code, target in sorted(mapping.items()):
            print(f"{code}\t{target}")
        # Stale permalinks cannot be listed without querying the bucket, so a
        # dry run stays purely local. A real run prints each deletion before
        # making it.
        print(
            f"\n{len(mapping)} permalinks -> {', '.join(resolve_targets())}"
            f"\nnothing written; deletions are only known once a bucket is listed",
            file=sys.stderr,
        )
        return 0

    s3 = s3_client()
    for bucket in resolve_targets():
        reconcile(s3, bucket, mapping)
    return 0


if __name__ == "__main__":
    sys.exit(main())
