"""Upload the built site/ to every bucket in databags/deploy_targets.yaml.

The single deploy mechanism for every workflow that publishes the site.
Bucket list comes from utils/deploy_targets.py, archive scope from
utils/selective_build_sync_args.py — neither is written down twice.

    python utils/deploy_to_s3.py --scope full                 # everything in site/
    python utils/deploy_to_s3.py --scope archive              # every edition
    python utils/deploy_to_s3.py --scope archive --year 2026  # one edition
    python utils/deploy_to_s3.py --scope full --dry-run

Scope selects which slice of site/ to upload, not what was built. A
BUILD_MODE=current build produces only current-edition artifacts, so
--scope full is correct there: it uploads everything that was rendered.

--year narrows the upload, never the render. The archive job always renders
everything, because a partial render would leave Pagefind indexing a fraction
of the site and overwrite the complete index. Rendering is the cheap part
(~106 s); the upload is what costs minutes, so that is what gets scoped.

Invariant (plans/selective-builds.md): never pass --delete to the site-wide
sync. Production builds render a fraction of the site, so a deleting sync
would strip the archive out of the bucket.

The one exception is narrow and opt-in: --scope full mirrors each folder in
`mirror_prefixes` (databags/deploy_targets.yaml) with a delete-sync limited
to that folder, so pages removed from the repo also leave the bucket. Every
folder is checked before any bucket is touched: it must not overlap a path
that lives in S3 but not in a current build (the archive, the search index,
the talk permalinks), and it must exist and be non-empty in site/.

Only changed files are uploaded. `aws s3 sync` uploads a file when its size
differs or its local mtime is newer than the object's, and a CI build writes
every file fresh, so on its own it re-uploads all of site/ on every deploy.
Before each bucket's sync, files whose content matches the object (same size,
same S3 ETag) are backdated so sync skips them; everything else is uploaded.
A wrong or missing match only ever costs an upload, never skips a change.

Each bucket gets a complete, independent copy — nothing here makes one
bucket depend on another. Buckets are synced in list order and the first
failure aborts the run.

Credentials come from the usual AWS_* environment variables.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

import boto3
from deploy_targets import resolve_mirror_prefixes, resolve_targets
from selective_build_sync_args import sync_include_args
from talk_permalinks import PERMALINK_ROOT

REPO = Path(__file__).resolve().parent.parent
SITE_DIR = REPO / "site"
ARCHIVE_CONTENT = REPO / "content" / "archive"

SCOPES = ("full", "archive")
ALL_YEARS = "all"

# Lektor's build-state database. Not part of the site, ~13 MB, and served
# publicly if it is uploaded — which it was, until this exclusion existed.
BUILD_STATE_EXCLUDE = [".lektor/*"]

# The search index covers the whole site and is rebuilt on every archive run,
# so it has to ship with every archive upload or the deployed index drifts out
# of step with the content it describes.
SEARCH_INDEX_INCLUDE = ["pagefind/*"]

# The aws CLI's defaults: files of 8 MiB or more go up in 8 MiB parts, and a
# multipart object's ETag is the MD5 of the parts' MD5s, suffixed "-{parts}".
MULTIPART_THRESHOLD = 8 * 1024 * 1024
MULTIPART_CHUNKSIZE = 8 * 1024 * 1024

# Older than any object, so sync treats a same-size file as already uploaded.
UNCHANGED_MTIME = 0


def s3_only_roots() -> list[str]:
    """Bucket paths a current build does not render: the archive subtrees,
    the search index and the talk permalinks. A delete-sync over any of them
    would remove live content. Derived from the same sources that define them.
    """
    patterns = sync_include_args()[1::2] + SEARCH_INDEX_INCLUDE
    return [pattern.removesuffix("/*") for pattern in patterns] + [PERMALINK_ROOT]


def overlaps(a: str, b: str) -> bool:
    """True when one bucket path is the other or lies inside it."""
    return a == b or a.startswith(f"{b}/") or b.startswith(f"{a}/")


def checked_mirror_prefixes() -> list[str]:
    """The configured mirror folders, refused before any upload if unsafe."""
    prefixes = resolve_mirror_prefixes()
    protected = s3_only_roots()
    problems: list[str] = []
    for prefix in prefixes:
        clashes = [root for root in protected if overlaps(prefix, root)]
        if clashes:
            problems.append(
                f"'{prefix}' overlaps {', '.join(clashes)}, which lives in S3 but "
                f"not in a current build — a delete-sync would remove it."
            )
            continue
        folder = SITE_DIR / prefix
        if not folder.is_dir() or not any(f.is_file() for f in folder.rglob("*")):
            problems.append(
                f"'{prefix}' is missing or empty in {SITE_DIR}. Mirroring it would "
                f"empty s3://<bucket>/{prefix}/. If the folder is unpublished on "
                f"purpose, remove it from mirror_prefixes first."
            )
    if problems:
        raise SystemExit(
            "Refusing to deploy, mirror_prefixes in databags/deploy_targets.yaml:\n  "
            + "\n  ".join(problems)
        )
    return prefixes


def mirror_cmd(prefix: str, bucket: str) -> list[str]:
    # Both ends carry a trailing slash: S3 keys match by plain string prefix,
    # so 's3://b/sponsors' would also cover a sibling like 'sponsors-old/'.
    return [
        "aws",
        "s3",
        "sync",
        f"{SITE_DIR / prefix}/",
        f"s3://{bucket}/{prefix}/",
        "--no-progress",
        "--delete",
    ]


def s3_etag(path: Path) -> str:
    """The ETag S3 assigns this file when the aws CLI uploads it unencrypted
    or with SSE-S3. Other encryption gives ETags that never match, which
    means a full upload, not a skipped change.
    """
    part_md5s: list[bytes] = []
    with path.open("rb") as f:
        while chunk := f.read(MULTIPART_CHUNKSIZE):
            part_md5s.append(hashlib.md5(chunk).digest())
    if path.stat().st_size < MULTIPART_THRESHOLD:
        return (part_md5s[0] if part_md5s else hashlib.md5(b"").digest()).hex()
    return f"{hashlib.md5(b''.join(part_md5s)).hexdigest()}-{len(part_md5s)}"


def local_fingerprints() -> dict[str, tuple[int, str]]:
    """Bucket key -> (size, ETag) for every file in site/ that sync may upload."""
    fingerprints: dict[str, tuple[int, str]] = {}
    for path in SITE_DIR.rglob("*"):
        key = path.relative_to(SITE_DIR).as_posix()
        if path.is_file() and not any(fnmatch(key, p) for p in BUILD_STATE_EXCLUDE):
            fingerprints[key] = (path.stat().st_size, s3_etag(path))
    return fingerprints


def remote_fingerprints(s3, bucket: str) -> dict[str, tuple[int, str]]:
    """Bucket key -> (size, ETag) for every object in the bucket."""
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=bucket)
    return {
        obj["Key"]: (obj["Size"], obj["ETag"].strip('"'))
        for page in pages
        for obj in page.get("Contents", [])
    }


def mark_unchanged(
    local: dict[str, tuple[int, str]], remote: dict[str, tuple[int, str]]
) -> int:
    """Backdate the files the bucket already holds; return how many.

    Every other file gets the current time, which is newer than any object,
    so the next sync uploads it. That reset matters from the second bucket
    on: a file backdated for one bucket may differ in the next.
    """
    unchanged = 0
    for key, fingerprint in local.items():
        path = SITE_DIR / key
        if remote.get(key) == fingerprint:
            os.utime(path, (UNCHANGED_MTIME, UNCHANGED_MTIME))
            unchanged += 1
        else:
            os.utime(path)
    return unchanged


def known_years() -> list[str]:
    """Editions that actually exist, so --year needs no hand-maintained list."""
    return sorted(
        p.name for p in ARCHIVE_CONTENT.iterdir() if p.is_dir() and p.name.isdigit()
    )


def narrow_to_year(patterns: list[str], year: str) -> list[str]:
    """Rewrite `--include archive/*` as `--include archive/{year}/*`.

    Works off the same patterns sync_include_args() derives from
    databags/selective_build.yaml, so the archive prefix is still named in
    exactly one place. A pattern that is not a directory wildcard cannot be
    narrowed by year, and guessing would silently upload the wrong subset.
    """
    out: list[str] = []
    for flag, pattern in zip(patterns[::2], patterns[1::2], strict=True):
        if not pattern.endswith("/*"):
            raise SystemExit(
                f"Cannot narrow {pattern!r} to a year: --year only applies to "
                f"year-partitioned subtrees. Check databags/selective_build.yaml."
            )
        out += [flag, f"{pattern[:-2]}/{year}/*"]
    return out


def sync_args(scope: str, year: str = ALL_YEARS) -> list[str]:
    """The --include/--exclude flags for a scope, in aws s3 sync order."""
    if scope == "full":
        selection: list[str] = []
    elif scope == "archive":
        includes = sync_include_args()
        if year != ALL_YEARS:
            includes = narrow_to_year(includes, year)
        selection = ["--exclude", "*", *includes]
        for pattern in SEARCH_INDEX_INCLUDE:
            selection += ["--include", pattern]
    else:  # argparse constrains this; belt and braces
        raise SystemExit(f"Unknown scope {scope!r}, expected one of {SCOPES}")
    for pattern in BUILD_STATE_EXCLUDE:
        selection += ["--exclude", pattern]
    return selection


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=SCOPES, required=True)
    parser.add_argument(
        "--year",
        default=ALL_YEARS,
        help=f"With --scope archive: one edition, or '{ALL_YEARS}' for every edition.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved buckets and the exact command, upload nothing.",
    )
    args = parser.parse_args()

    # Validated against the editions on disk rather than a list someone has to
    # remember to extend, so archiving a new edition needs no config change.
    if args.year != ALL_YEARS:
        if args.scope != "archive":
            raise SystemExit(
                f"--year only applies to --scope archive, not {args.scope!r}."
            )
        years = known_years()
        if args.year not in years:
            raise SystemExit(
                f"Unknown edition {args.year!r}. Available: {', '.join(years)}, "
                f"or '{ALL_YEARS}' for every edition."
            )

    # A green deploy of an empty directory is worse than a failed one.
    if not SITE_DIR.is_dir() or not any(SITE_DIR.iterdir()):
        raise SystemExit(
            f"Nothing to deploy: {SITE_DIR} is missing or empty. Run `make build` first."
        )

    buckets = resolve_targets()
    selection = sync_args(args.scope, args.year)
    # Only a current-edition deploy renders these folders completely; the
    # archive scope uploads a slice and must never delete anything.
    mirrors = checked_mirror_prefixes() if args.scope == "full" else []
    label = args.scope if args.year == ALL_YEARS else f"{args.scope} {args.year}"
    # A dry run stays local: which files are unchanged is only known once a
    # bucket is listed.
    s3 = None if args.dry_run else boto3.client("s3")
    local = None if args.dry_run else local_fingerprints()

    for bucket in buckets:
        cmd = [
            "aws",
            "s3",
            "sync",
            str(SITE_DIR),
            f"s3://{bucket}",
            "--no-progress",
            *selection,
        ]
        print(f"::group::{label} scope -> s3://{bucket}", flush=True)
        print(" ".join(cmd), flush=True)
        if not args.dry_run:
            unchanged = mark_unchanged(local, remote_fingerprints(s3, bucket))
            print(
                f"{unchanged} of {len(local)} files already in s3://{bucket}, "
                f"not uploaded again",
                flush=True,
            )
            # shell=False: '*' reaches aws as a literal argument, so no glob
            # guard is needed. check=True aborts before the next bucket.
            subprocess.run(cmd, check=True)
        # After the upload, so a page is never missing while it is replaced.
        for prefix in mirrors:
            mirror = mirror_cmd(prefix, bucket)
            print(" ".join(mirror), flush=True)
            if not args.dry_run:
                subprocess.run(mirror, check=True)
        print("::endgroup::", flush=True)

    if args.dry_run:
        print(f"Dry run — nothing uploaded. Targets: {', '.join(buckets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
