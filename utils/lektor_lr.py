"""Shared Lektor ``contents.lr`` parsing, serialisation and talk indexing.

Why this module exists
----------------------
Several utilities carried their own hand-rolled ``.lr`` parser, and they did
not agree. ``sync_recordings.py``'s variant split the file on ``\\n---\\n`` and
discarded any chunk whose first line contained no colon. Every Pretalx-code
redirect stub written by ``migrate_pretalx_slugs.py`` opens with a generator
comment::

    # migrate_pretalx_slugs.py — Pretalx code → slug redirect
    _model: redirect
    ---
    target: /archive/2026/talks/…/

so the whole first chunk was dropped, ``_model: redirect`` with it. Rewriting a
stub through that parser turned a 301 into an ordinary talk page — indexable,
duplicate, and admitted into the sitemap, which filters on
``_model == 'redirect'``.

Three rules follow, and this module exists to enforce them:

1. **Resolve talks by their ``code:`` field, never by folder name.** After the
   slug migration the folder named by a Pretalx code *is* the redirect stub;
   the real page lives in a slug-named sibling. :func:`build_code_index` is the
   only supported lookup.
2. **Untouched fields are preserved byte for byte.** Every field keeps its
   original source lines and is re-emitted verbatim unless a caller changes its
   value, so a write can only ever alter the fields it was asked to alter.
   Unrecognised lines (generator comments) ride along as the *lead* of the
   field that follows them.
3. **A writer refuses a file that does not round-trip.** :func:`round_trip_ok`
   re-serialises a freshly parsed file and compares; a mismatch means the
   parser failed to capture some line, and guessing is not an option.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PRETALX_CONFIG = REPO_ROOT / "databags" / "pretalx.yaml"

FIELD_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s?(.*)$")


@dataclass
class Field:
    """One ``name: value`` record in a ``contents.lr`` file.

    ``lead`` holds the lines that preceded this field inside the same
    ``---``-delimited chunk and that are not themselves fields — generator
    comments, mostly. A Field with an empty ``name`` is lead-only: trailing
    lines that no field followed.

    ``raw`` is the field's exact source lines, used verbatim on serialisation.
    :func:`upsert_fields` clears it for the fields it changes, so those are
    re-rendered canonically while everything else stays byte-identical. A
    freshly constructed Field has ``raw is None`` and is always canonical.

    ``block`` records which of Lektor's two spellings the field used — inline
    (``title: Talks``) or block (``body:``, blank line, text). A single-line
    value may legitimately use either, and hundreds of talk files use block
    form, so the flag is what lets a changed field keep its original shape.
    """

    name: str
    value: str = ""
    lead: tuple[str, ...] = dataclass_field(default_factory=tuple)
    block: bool = False
    raw: tuple[str, ...] | None = None


def parse_lr(text: str) -> list[Field]:
    """Parse a ``contents.lr`` into ordered :class:`Field` records.

    Lektor writes a multi-line field as ``name:``, a blank line, then the body.
    That blank line belongs to the separator rather than the value, so it is
    stripped from ``value`` and re-added on canonical output — otherwise every
    round trip would grow the file by one blank line per block field.
    """
    fields: list[Field] = []
    name: str | None = None
    buf: list[str] = []
    raw: list[str] = []
    lead: list[str] = []
    inline = False

    def flush() -> None:
        nonlocal name, buf, raw, lead, inline
        if name is None:
            return
        value = "\n".join(buf).rstrip("\n")
        if not inline and value.startswith("\n"):
            value = value[1:]
        fields.append(
            Field(name, value, tuple(lead), block=not inline, raw=tuple(raw))
        )
        name, buf, raw, lead, inline = None, [], [], [], False

    for line in text.split("\n"):
        if line == "---":
            flush()
            continue
        if name is None:
            m = FIELD_RE.match(line)
            if not m:
                # Not a field — a comment or stray line. Keep it, attached to
                # whatever field follows so it survives serialisation.
                lead.append(line)
                continue
            name = m.group(1)
            rest = m.group(2)
            inline = bool(rest)
            buf = [rest] if rest else []
            raw = [line]
        else:
            buf.append(line)
            raw.append(line)
    flush()

    if lead:
        # Trailing lines with no field after them — including the empty string
        # that a file-final newline produces.
        fields.append(Field("", "", tuple(lead)))
    return fields


def serialize_lr(fields: list[Field]) -> str:
    """Render :class:`Field` records back into ``contents.lr`` text.

    Output always ends with exactly one newline. A handful of hand-authored
    static pages in ``content/`` lack a final newline and therefore fail
    :func:`round_trip_ok` — deliberately, in the safe direction: a writer
    refuses them rather than silently reformatting. No importer targets those
    pages; every talk and speaker file round-trips.
    """
    out: list[str] = []
    for i, f in enumerate(fields):
        if i > 0:
            out.append("---")
        out.extend(f.lead)
        if f.raw is not None:
            out.extend(f.raw)
            continue
        if not f.name:
            continue
        if not f.value:
            # An empty value is always the bare `name:` form; a block here
            # would emit stray blank lines.
            out.append(f"{f.name}:")
        elif f.block or "\n" in f.value:
            out.append(f"{f.name}:")
            out.append("")
            out.append(f.value)
        else:
            out.append(f"{f.name}: {f.value}")
    text = "\n".join(out)
    if not text.endswith("\n"):
        text += "\n"
    return text


def round_trip_ok(text: str, fields: list[Field]) -> bool:
    """True when re-serialising a freshly parsed file reproduces it exactly."""
    return serialize_lr(fields) == text


def field_value(fields: list[Field], name: str, default: str | None = None) -> str | None:
    for f in fields:
        if f.name == name:
            return f.value
    return default


def upsert_fields(fields: list[Field], values: dict[str, str]) -> list[Field]:
    """Set each ``name: value`` in place, appending the ones not yet present.

    Only fields whose value actually changes are re-rendered; the rest keep
    their verbatim source. New fields are appended before any trailing
    lead-only record so the file-final newline stays last.
    """
    seen: set[str] = set()
    for f in fields:
        if f.name not in values:
            continue
        seen.add(f.name)
        if f.value != values[f.name]:
            f.value = values[f.name]
            f.raw = None

    new = [Field(n, v) for n, v in values.items() if n not in seen]
    if not new:
        return fields

    tail = 1 if fields and not fields[-1].name else 0
    at = len(fields) - tail
    if at:
        # The file-final newline is captured as a trailing empty line on the
        # last field. Appending after it would leave a stray blank line before
        # the new `---` separator, so drop it here; serialisation re-adds the
        # newline at the true end of the file.
        prev = fields[at - 1]
        if prev.raw is not None:
            trimmed = list(prev.raw)
            while trimmed and not trimmed[-1]:
                trimmed.pop()
            prev.raw = tuple(trimmed)
    fields[at:at] = new
    return fields


def is_redirect(fields: list[Field]) -> bool:
    return field_value(fields, "_model") == "redirect"


def read_lr(path: Path) -> tuple[str, list[Field]]:
    """Return ``(raw_text, fields)`` for a ``contents.lr``."""
    text = path.read_text(encoding="utf-8")
    return text, parse_lr(text)


def write_lr(path: Path, fields: list[Field]) -> None:
    path.write_text(serialize_lr(fields), encoding="utf-8")


def build_code_index(talks_dir: Path) -> dict[str, Path]:
    """Map each talk's Pretalx ``code:`` to its canonical folder.

    After the slug migration the folder name is the slug, so a name-based
    lookup would land on the ``_model: redirect`` sibling instead of the talk.
    Redirect stubs are skipped, so a code can only ever resolve to a real page.

    Raises on a duplicate code: two folders claiming one code means the content
    tree is inconsistent, and a writer must not guess which one to pick.
    """
    index: dict[str, Path] = {}
    if not talks_dir.is_dir():
        return index
    for entry in sorted(talks_dir.iterdir()):
        if not entry.is_dir():
            continue
        lr = entry / "contents.lr"
        if not lr.exists():
            continue
        fields = parse_lr(lr.read_text(encoding="utf-8", errors="ignore"))
        if is_redirect(fields):
            continue
        code = (field_value(fields, "code") or "").strip()
        if not code:
            continue
        if code in index:
            raise ValueError(
                f"Duplicate talk code {code!r}: {index[code].name} and {entry.name}"
            )
        index[code] = entry
    return index


def current_year() -> str:
    """The in-flight edition's year, per ``databags/pretalx.yaml``."""
    if not PRETALX_CONFIG.exists():
        return ""
    with PRETALX_CONFIG.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return str(cfg.get("events", {}).get("current", {}).get("year", ""))


def talks_dir_for_year(year: str) -> Path:
    """Current edition lives at /talks/, every other edition under /archive/."""
    if year == current_year():
        return REPO_ROOT / "content" / "talks"
    return REPO_ROOT / "content" / "archive" / year / "talks"
