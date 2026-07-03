"""Scope a Lektor build to the current edition (selective builds).

BUILD_MODE=current skips BUILDING the archive-scoped artifacts (past
editions, attendee certificates), so production deploys only re-render
the current-edition pages (~12% of the site). Because the production S3
sync never deletes, the previously deployed archive stays live — it just
stops being rebuilt.

Crucially the filter applies to the build traversal, NOT to record
discovery: every page that does render — homepage, sitemap segments,
topic hubs, llms.txt — still sees the full record tree and renders
byte-identically in every mode. (Filtering discovery instead would make
cross-edition pages like the homepage's latest-videos section render
incomplete and overwrite their complete versions in S3.) Artifacts are
therefore mode-independent in content; modes only decide which artifacts
get (re)built.

BUILD_MODE=archive and BUILD_MODE=full build everything; the differences
between them (Pagefind, S3 sync scope) live in the Makefile and the
GitHub Actions workflows, not here. Without BUILD_MODE set (plain
`lektor build`, `lektor server`), the plugin does nothing.

The exclusion list lives in databags/selective_build.yaml — the on-demand
archive workflow derives its S3 sync scope from the same file. Full
design: plans/selective-builds.md.

Mechanism: ``PageBuildProgram.iter_child_sources`` is how ``build_all``
descends into child records — wrapping it keeps excluded subtrees out of
the build queue while template queries (``Database.iter_items``) stay
untouched.
"""

import os
from pathlib import Path

import yaml
from lektor.build_programs import PageBuildProgram
from lektor.pluginsystem import Plugin

VALID_MODES = ("current", "archive", "full")
CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "databags" / "selective_build.yaml"

# Record paths whose artifacts are skipped; empty means build everything.
# Module state (not a closure) so repeated plugin setups — e.g. dev-server
# restarts in one process — always reflect the latest BUILD_MODE.
_state: dict[str, tuple[str, ...]] = {"excludes": ()}


def load_current_excludes() -> tuple[str, ...]:
    """Read the exclusion list; fail hard on a missing or empty config."""
    if not CONFIG_FILE.exists():
        raise RuntimeError(f"selective-build: config file not found: {CONFIG_FILE}")
    data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    excludes = data.get("current_excludes")
    if not excludes:
        raise RuntimeError(f"selective-build: 'current_excludes' missing or empty in {CONFIG_FILE}")
    invalid = [p for p in excludes if not isinstance(p, str) or not p.startswith("/")]
    if invalid:
        raise RuntimeError(f"selective-build: record paths must start with '/': {invalid}")
    return tuple(p.rstrip("/") for p in excludes)


def _install_build_filter() -> None:
    """Wrap PageBuildProgram.iter_child_sources once; follows _state."""
    if getattr(PageBuildProgram.iter_child_sources, "_selective_build", False):
        return
    original = PageBuildProgram.iter_child_sources

    def iter_child_sources(self):
        excluded = _state["excludes"]
        if not excluded:
            yield from original(self)
            return
        prefixes = tuple(e + "/" for e in excluded)
        for source in original(self):
            path = getattr(source, "path", None)
            if path is not None and (path in excluded or path.startswith(prefixes)):
                continue
            yield source

    iter_child_sources._selective_build = True
    PageBuildProgram.iter_child_sources = iter_child_sources


class SelectiveBuildPlugin(Plugin):
    name = "selective-build"
    description = "Scope builds via BUILD_MODE: current | archive | full."

    def on_setup_env(self, **_extra):
        mode = os.environ.get("BUILD_MODE") or None
        if mode is None:
            _state["excludes"] = ()
            return
        if mode not in VALID_MODES:
            raise RuntimeError(
                f"selective-build: unknown BUILD_MODE {mode!r}; expected one of {VALID_MODES}"
            )
        # Validate the config in every mode: the archive deploy derives its
        # S3 sync scope from the same file, so a broken config must fail the
        # build, not surface later as a silently empty deploy.
        excludes = load_current_excludes()
        if mode != "current":
            _state["excludes"] = ()
            print(f"[selective-build] BUILD_MODE={mode}: building everything")
            return
        _state["excludes"] = excludes
        _install_build_filter()
        print(
            f"[selective-build] BUILD_MODE=current: not building "
            f"{len(excludes)} subtrees: {', '.join(excludes)}"
        )
