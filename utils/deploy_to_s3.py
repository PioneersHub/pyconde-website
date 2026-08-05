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

Invariant (plans/selective-builds.md): never pass --delete. Production
builds render a fraction of the site, so a deleting sync would strip the
archive out of the bucket.

Each bucket gets a complete, independent copy — nothing here makes one
bucket depend on another. Buckets are synced in list order and the first
failure aborts the run.

Credentials come from the usual AWS_* environment variables.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from deploy_targets import resolve_targets
from selective_build_sync_args import sync_include_args

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
    label = args.scope if args.year == ALL_YEARS else f"{args.scope} {args.year}"

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
            # shell=False: '*' reaches aws as a literal argument, so no glob
            # guard is needed. check=True aborts before the next bucket.
            subprocess.run(cmd, check=True)
        print("::endgroup::", flush=True)

    if args.dry_run:
        print(f"Dry run — nothing uploaded. Targets: {', '.join(buckets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
