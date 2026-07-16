"""Emit `aws s3 sync` --include arguments for the archive-scope deploy.

Reads databags/selective_build.yaml — the same list the selective-build
Lektor plugin uses to exclude subtrees from BUILD_MODE=current renders —
and maps each record path to the artifact pattern it produces in site/:
a path whose last segment has a file extension renders as a single file
(e.g. /llms.txt, /sitemaps/tracks.xml), everything else as a directory.

Used by .github/workflows/archive-build.yml so that build scope and
deploy scope cannot drift apart. See plans/selective-builds.md.
"""

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO / "databags" / "selective_build.yaml"


def sync_include_args() -> list[str]:
    data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    excludes = data.get("current_excludes")
    if not excludes:
        raise SystemExit(f"'current_excludes' missing or empty in {CONFIG_FILE}")
    args: list[str] = []
    for record_path in excludes:
        rel = record_path.lstrip("/")
        pattern = rel if "." in rel.rsplit("/", 1)[-1] else f"{rel}/*"
        args += ["--include", pattern]
    return args


if __name__ == "__main__":
    print(" ".join(sync_include_args()))
