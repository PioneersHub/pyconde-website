"""
Migrate every talk so its URL is a slug, with the Pretalx code redirecting.

For each `talks/` directory under content/ and content/archive/{year}/:

  Before:
    talks/3VYSMS/contents.lr           code=3VYSMS, title="You don't think…"
  After:
    talks/you-dont-think-about-your-streamlit-app/contents.lr   slug added
    talks/3VYSMS/contents.lr                                    _model=redirect → target=/…/talks/{slug}/

Each speaker's `talks:` field — a newline-separated list of Pretalx codes —
is rewritten to use slugs so `site.get(talks_root + '/' + reference)`
keeps working in templates without further changes.

Companion nginx / Caddy snippets land in site-config/ for the hoster.

Slug rules:
  • derived from `title` via slugify (NFKD strip → ascii → lowercase →
    non-alnum collapsed to `-`)
  • if two talks in the same edition resolve to the same slug, the
    losing entries get `-{lowercased-code}` appended (deterministic by
    code sort order)
  • slug, once written into contents.lr, is treated as immutable; the
    script never overwrites an existing slug.

Idempotent: re-running with already-migrated content is a no-op.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTENT = REPO / "content"
NGINX_OUT = REPO / "site-config" / "pretalx-redirects.nginx.conf"
CADDY_OUT = REPO / "site-config" / "Caddyfile.pretalx-redirects"

REDIRECT_MARKER = "# migrate_pretalx_slugs.py — Pretalx code → slug redirect"


def slugify(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def parse_lr(text: str) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    cur_name: str | None = None
    cur_buf: list[str] = []
    inline = False
    for line in text.split("\n"):
        if line == "---":
            if cur_name is not None:
                value = "\n".join(cur_buf).rstrip("\n")
                if not inline and value.startswith("\n"):
                    value = value[1:]
                fields.append((cur_name, value))
            cur_name = None
            cur_buf = []
            inline = False
            continue
        if cur_name is None:
            m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s?(.*)$", line)
            if not m:
                continue
            cur_name = m.group(1)
            rest = m.group(2)
            if rest:
                inline = True
                cur_buf = [rest]
            else:
                inline = False
                cur_buf = []
        else:
            cur_buf.append(line)
    if cur_name is not None:
        value = "\n".join(cur_buf).rstrip("\n")
        if not inline and value.startswith("\n"):
            value = value[1:]
        fields.append((cur_name, value))
    return fields


def serialize_lr(fields: list[tuple[str, str]]) -> str:
    out: list[str] = []
    for i, (name, value) in enumerate(fields):
        if i > 0:
            out.append("---")
        if "\n" in value:
            out.append(f"{name}:")
            out.append("")
            out.append(value)
        else:
            out.append(f"{name}: {value}" if value else f"{name}:")
    return "\n".join(out) + "\n"


def upsert_field(fields: list[tuple[str, str]], name: str, value: str, *, after: str | None = None) -> list[tuple[str, str]]:
    for i, (n, _) in enumerate(fields):
        if n == name:
            fields[i] = (name, value)
            return fields
    if after:
        for i, (n, _) in enumerate(fields):
            if n == after:
                fields.insert(i + 1, (name, value))
                return fields
    fields.append((name, value))
    return fields


def read_lr(p: Path) -> list[tuple[str, str]]:
    return parse_lr(p.read_text(encoding="utf-8"))


def write_lr(p: Path, fields: list[tuple[str, str]]) -> None:
    p.write_text(serialize_lr(fields), encoding="utf-8")


def is_redirect(fields: list[tuple[str, str]]) -> bool:
    for name, value in fields:
        if name == "_model" and value == "redirect":
            return True
    return False


def field_value(fields: list[tuple[str, str]], name: str) -> str | None:
    for n, v in fields:
        if n == name:
            return v
    return None


def plan_for_edition(talks_dir: Path) -> dict[str, str]:
    """
    Walk talks_dir, return mapping {old_folder_name → new_folder_name} where
    new_folder_name is either an existing slug-named folder (already
    migrated) or a freshly-computed slug. Old name = current folder name.
    """
    plan: dict[str, str] = {}
    # First pass: collect every (folder_name, code, slug, title)
    items: list[tuple[str, str, str, str]] = []
    for d in sorted(talks_dir.iterdir()):
        if not d.is_dir():
            continue
        lr = d / "contents.lr"
        if not lr.exists():
            continue
        fields = read_lr(lr)
        if is_redirect(fields):
            continue
        code = field_value(fields, "code") or d.name
        title = field_value(fields, "title") or ""
        slug = field_value(fields, "slug") or ""
        items.append((d.name, code, slug, title))

    desired: dict[str, str] = {}
    used_slugs: dict[str, str] = {}  # slug → first folder claiming it
    for old, code, slug, title in items:
        if slug:
            desired[old] = slug
            used_slugs[slug] = old
        else:
            desired[old] = ""  # placeholder, filled below

    for old, code, slug, title in items:
        if desired[old]:
            continue
        base = slugify(title) or slugify(code) or "talk"
        candidate = base
        if candidate in used_slugs and used_slugs[candidate] != old:
            candidate = f"{base}-{code.lower()}"
        used_slugs[candidate] = old
        desired[old] = candidate
    return desired


def migrate_talks(talks_dir: Path, dry_run: bool) -> dict[str, str]:
    """Rename talk folders to slug and add `slug:` field. Return {code: slug}."""
    desired = plan_for_edition(talks_dir)
    code_to_slug: dict[str, str] = {}
    for old, new in desired.items():
        old_dir = talks_dir / old
        lr = old_dir / "contents.lr"
        if not lr.exists():
            continue
        fields = read_lr(lr)
        code = field_value(fields, "code") or old
        code_to_slug[code] = new
        if old == new:
            # Already slug-named, just ensure `slug:` field present
            existing_slug = field_value(fields, "slug") or ""
            if existing_slug == new:
                continue
            fields = upsert_field(fields, "slug", new, after="code")
            if not dry_run:
                write_lr(lr, fields)
            continue
        new_dir = talks_dir / new
        if new_dir.exists():
            print(f"  conflict: {new_dir} already exists; skipping rename of {old_dir}", file=sys.stderr)
            continue
        fields = upsert_field(fields, "slug", new, after="code")
        if dry_run:
            print(f"  would rename {old_dir.name}/ → {new}/  (slug field set)")
        else:
            write_lr(lr, fields)
            old_dir.rename(new_dir)
    return code_to_slug


def write_redirect_pages(talks_dir: Path, code_to_slug: dict[str, str], talks_url_prefix: str, dry_run: bool) -> int:
    """Create sibling folders named by CODE that 301 → /{talks_url_prefix}/{slug}/.

    Assumes talk folders have already been renamed to their slugs, so the
    CODE-named slot is free (or contains a stale redirect from a prior run).
    """
    written = 0
    for code, slug in code_to_slug.items():
        if code == slug:
            continue
        redir_dir = talks_dir / code
        if dry_run:
            print(f"  would write redirect {code} → {slug}")
            written += 1
            continue
        # If something other than our redirect lives here, refuse to clobber.
        if redir_dir.exists():
            lr = redir_dir / "contents.lr"
            if not (lr.exists() and REDIRECT_MARKER in lr.read_text(encoding="utf-8")):
                print(f"  skip redirect {code}: folder exists and is not a managed redirect", file=sys.stderr)
                continue
        redir_dir.mkdir(parents=True, exist_ok=True)
        body = (
            f"{REDIRECT_MARKER}\n"
            f"_model: redirect\n"
            f"---\n"
            f"target: {talks_url_prefix}/{slug}/\n"
            f"---\n"
            f"status: 301\n"
            f"---\n"
            f"note: Pretalx code → slug for {code}\n"
        )
        (redir_dir / "contents.lr").write_text(body, encoding="utf-8")
        written += 1
    return written


def migrate_speakers(speakers_dir: Path, code_to_slug: dict[str, str], dry_run: bool) -> int:
    """Rewrite each speaker's `talks:` field replacing codes with slugs."""
    if not speakers_dir.is_dir():
        return 0
    changed = 0
    for sp_dir in sorted(speakers_dir.iterdir()):
        if not sp_dir.is_dir():
            continue
        lr = sp_dir / "contents.lr"
        if not lr.exists():
            continue
        fields = read_lr(lr)
        talks_value = field_value(fields, "talks")
        if not talks_value:
            continue
        new_value_lines: list[str] = []
        modified = False
        for line in talks_value.split("\n"):
            stripped = line.strip()
            if stripped and stripped in code_to_slug:
                slug = code_to_slug[stripped]
                if slug != stripped:
                    modified = True
                new_value_lines.append(slug)
            else:
                new_value_lines.append(line)
        if not modified:
            continue
        fields = upsert_field(fields, "talks", "\n".join(new_value_lines))
        if dry_run:
            print(f"  would update speaker {sp_dir.name}")
        else:
            write_lr(lr, fields)
        changed += 1
    return changed


def write_server_snippets(all_redirects: list[tuple[str, str]]) -> None:
    NGINX_OUT.parent.mkdir(parents=True, exist_ok=True)
    nginx_lines = [
        "# Generated by utils/migrate_pretalx_slugs.py — DO NOT EDIT.",
        "# Paste into the relevant nginx `server { ... }` block.",
        "",
    ]
    caddy_lines = [
        "# Generated by utils/migrate_pretalx_slugs.py — DO NOT EDIT.",
        "# Drop into the relevant Caddyfile site block.",
        "",
    ]
    for src, dst in all_redirects:
        nginx_lines.append(f"location = {src} {{ return 301 {dst}; }}")
        caddy_lines.append(f"redir {src} {dst} 301")
    NGINX_OUT.write_text("\n".join(nginx_lines) + "\n", encoding="utf-8")
    CADDY_OUT.write_text("\n".join(caddy_lines) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    everything: list[tuple[str, str]] = []  # (old_url, new_url) for server snippets

    # Editions: current /talks/ + every /archive/{year}/talks/
    editions: list[tuple[Path, Path, str, str]] = []
    cur_talks = CONTENT / "talks"
    cur_speakers = CONTENT / "speakers"
    if cur_talks.is_dir():
        editions.append((cur_talks, cur_speakers, "/talks", "current"))
    for year_dir in sorted((CONTENT / "archive").iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        editions.append((
            year_dir / "talks",
            year_dir / "speakers",
            f"/archive/{year_dir.name}/talks",
            year_dir.name,
        ))

    grand_renames = 0
    grand_redirects = 0
    grand_speakers = 0
    for talks_dir, speakers_dir, url_prefix, label in editions:
        if not talks_dir.is_dir():
            continue
        print(f"-- edition {label} ({talks_dir.relative_to(REPO)}) --")
        code_to_slug = migrate_talks(talks_dir, dry_run=args.dry_run)
        renamed = sum(1 for c, s in code_to_slug.items() if c != s)
        grand_renames += renamed
        n_speakers = migrate_speakers(speakers_dir, code_to_slug, dry_run=args.dry_run)
        grand_speakers += n_speakers
        n_redirs = write_redirect_pages(talks_dir, code_to_slug, url_prefix, dry_run=args.dry_run)
        grand_redirects += n_redirs
        for code, slug in code_to_slug.items():
            if code != slug:
                everything.append((f"{url_prefix}/{code}/", f"{url_prefix}/{slug}/"))
        print(f"   talks renamed: {renamed}   speakers updated: {n_speakers}   redirects written: {n_redirs}")

    if not args.dry_run and everything:
        write_server_snippets(everything)
        print(f"server snippets: {NGINX_OUT.name}, {CADDY_OUT.name}")

    print()
    print(f"TOTAL: talks renamed {grand_renames}, speakers updated {grand_speakers}, redirects {grand_redirects}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
