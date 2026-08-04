"""Upload the built site/ to every bucket in databags/deploy_targets.yaml.

The single deploy mechanism for every workflow that publishes the site.
Bucket list comes from utils/deploy_targets.py, archive scope from
utils/selective_build_sync_args.py — neither is written down twice.

    python utils/deploy_to_s3.py --scope full        # everything in site/
    python utils/deploy_to_s3.py --scope archive     # archive scope only
    python utils/deploy_to_s3.py --scope full --dry-run

Scope selects which slice of site/ to upload, not what was built. A
BUILD_MODE=current build produces only current-edition artifacts, so
--scope full is correct there: it uploads everything that was rendered.

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

SCOPES = ("full", "archive")

# Lektor's build-state database. Not part of the site, ~13 MB, and served
# publicly if it is uploaded — which it was, until this exclusion existed.
BUILD_STATE_EXCLUDE = [".lektor/*"]


def sync_args(scope: str) -> list[str]:
    """The --include/--exclude flags for a scope, in aws s3 sync order."""
    if scope == "full":
        selection: list[str] = []
    elif scope == "archive":
        selection = ["--exclude", "*", *sync_include_args()]
    else:  # argparse constrains this; belt and braces
        raise SystemExit(f"Unknown scope {scope!r}, expected one of {SCOPES}")
    for pattern in BUILD_STATE_EXCLUDE:
        selection += ["--exclude", pattern]
    return selection


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=SCOPES, required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved buckets and the exact command, upload nothing.",
    )
    args = parser.parse_args()

    # A green deploy of an empty directory is worse than a failed one.
    if not SITE_DIR.is_dir() or not any(SITE_DIR.iterdir()):
        raise SystemExit(
            f"Nothing to deploy: {SITE_DIR} is missing or empty. Run `make build` first."
        )

    buckets = resolve_targets()
    selection = sync_args(args.scope)

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
        print(f"::group::{args.scope} scope -> s3://{bucket}", flush=True)
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
