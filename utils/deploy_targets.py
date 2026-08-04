"""Resolve the S3 buckets that production deploys write to.

Reads databags/deploy_targets.yaml and prints one bucket name per line, in
file order. Every workflow that uploads the site or configures a bucket
calls this, so a target can never be added to one workflow and forgotten
in another — the failure that took /archive/ offline in July 2026.

An entry is either a literal bucket name or `env:VARNAME`, resolved from
the environment so a name that should stay out of this public repository
can come from a GitHub secret instead.

Every failure is fatal. An unresolvable entry must not degrade into a
shorter bucket list: that turns a broken deploy into a green one that
uploads nowhere anybody serves.

    python utils/deploy_targets.py
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO / "databags" / "deploy_targets.yaml"

ENV_PREFIX = "env:"
# s3 naming rules, restricted to what a static-website bucket can be:
# 3-63 chars, lowercase alphanumeric plus dot and hyphen, no leading or
# trailing separator. Catches a stray quote or a path fragment in the
# secret before it is interpolated into an s3:// URI.
BUCKET_NAME = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


def resolve_targets() -> list[str]:
    if not CONFIG_FILE.exists():
        raise SystemExit(f"Missing required config: {CONFIG_FILE}")
    data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    entries = data.get("buckets")
    if not entries:
        raise SystemExit(f"'buckets' missing or empty in {CONFIG_FILE}")

    names: list[str] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, str):
            raise SystemExit(f"buckets[{i}] must be a string, got {entry!r}")

        if entry.startswith(ENV_PREFIX):
            var = entry[len(ENV_PREFIX) :]
            name = os.environ.get(var, "").strip()
            if not name:
                raise SystemExit(
                    f"buckets[{i}] is '{entry}' but ${var} is unset or empty. "
                    f"Set it in the workflow's env: block, or remove the entry "
                    f"from {CONFIG_FILE.name} if that target is retired."
                )
        else:
            name = entry.strip()

        if not BUCKET_NAME.match(name):
            raise SystemExit(
                f"buckets[{i}] does not resolve to a bucket name: {name!r}"
            )
        if name in names:
            # Silently deduplicating would hide a finished migration behind a
            # double upload. Say so instead, and name the fix.
            raise SystemExit(
                f"buckets[{i}] ('{entry}') resolves to {name!r}, which is already "
                f"listed. Remove the duplicate from {CONFIG_FILE.name}."
            )
        names.append(name)
    return names


if __name__ == "__main__":
    print("\n".join(resolve_targets()))
