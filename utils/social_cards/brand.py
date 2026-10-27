"""Load the PyCon DE card brand specification.

Two files feed the spec: ``brand.yaml`` next to this module (visual rules)
and ``databags/branding.yaml`` (event name, dates, venue — shared with the
website). Every value the engine draws comes from here; layout code never
hardcodes a colour, size or event fact.
"""

from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = Path(__file__).with_name("brand.yaml")
BRANDING_PATH = REPO_ROOT / "databags" / "branding.yaml"


SRGB_LINEAR_LIMIT = 0.03928


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [
        c / 12.92 if c <= SRGB_LINEAR_LIMIT else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    """WCAG 2 contrast ratio of two hex colours."""
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# Wider than this, a card is laid out in columns rather than rows.
LANDSCAPE_RATIO = 1.3


class BrandSpecError(ValueError):
    """The brand specification is incomplete or inconsistent."""


@dataclass(frozen=True)
class Format:
    name: str
    width: int
    height: int
    export_scale: int
    type_scale: float
    unit: float
    margin: float
    safe_top: float
    safe_bottom: float

    @property
    def landscape(self) -> bool:
        return self.width / self.height > LANDSCAPE_RATIO

    def px(self, reference_px: float) -> float:
        """Convert a size given for the 1200 px reference canvas."""
        return reference_px * self.type_scale * self.width / 1200


@dataclass(frozen=True)
class EventFacts:
    name: str
    start: date
    end: date
    venue: str


@dataclass(frozen=True, eq=False)
class Brand:
    """Hashed by identity: there is one spec per process (load_brand)."""

    raw: dict[str, Any]
    event: EventFacts

    @property
    def palette(self) -> dict[str, str]:
        return self.raw["palette"]

    def color(self, name: str) -> str:
        try:
            return self.palette[name]
        except KeyError:
            raise BrandSpecError(f"'{name}' is not a palette colour") from None

    def field(self, name: str) -> dict[str, Any]:
        try:
            return self.raw["fields"][name]
        except KeyError:
            raise BrandSpecError(f"'{name}' is not an approved card field") from None

    def role(self, name: str) -> dict[str, Any]:
        return self.raw["roles"][name]

    def font_path(self, key: str) -> Path:
        return REPO_ROOT / self.raw["fonts"][key]

    def logo_path(self, color: str) -> Path:
        return REPO_ROOT / self.raw["logo"]["files"][color]

    def format(self, name: str) -> Format:
        try:
            f = self.raw["formats"][name]
        except KeyError:
            raise BrandSpecError(f"unknown export format '{name}'") from None
        width, height = f["size"]
        return Format(
            name=name,
            width=width,
            height=height,
            export_scale=f["export_scale"],
            type_scale=f["type_scale"],
            unit=f["unit"],
            margin=f["unit"] * f["margin_units"],
            safe_top=f["safe_top"],
            safe_bottom=f["safe_bottom"],
        )

    def category(self, name: str) -> dict[str, Any]:
        try:
            return self.raw["categories"][name]
        except KeyError:
            known = ", ".join(self.raw["categories"])
            raise BrandSpecError(
                f"unknown category '{name}' (known: {known})"
            ) from None

    def month(self, lang: str, month: int) -> str:
        return self.raw["months"][lang][month - 1]

    def event_dates(self, lang: str) -> str:
        """'20–22 April 2027' / '20.–22. April 2027', from branding.yaml."""
        start, end = self.event.start, self.event.end
        month = self.month(lang, end.month)
        if start.month != end.month:
            raise BrandSpecError(
                "conference dates spanning two months are not supported"
            )
        if lang == "de":
            return f"{start.day}.–{end.day}. {month} {end.year}"
        return f"{start.day}–{end.day} {month} {end.year}"


def _parse_iso(value: str, key: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise BrandSpecError(
            f"databags/branding.yaml: dates.{key} must be an ISO date, got {value!r}"
        ) from None


def _load_event(branding: dict[str, Any], edition: int) -> EventFacts:
    dates = branding["dates"]
    location = branding["location"]
    start = _parse_iso(dates["start_iso"], "start_iso")
    if start.year != edition:
        raise BrandSpecError(
            f"brand.yaml is for {edition} but branding.yaml dates are {start.year}"
        )
    return EventFacts(
        name=f"PyCon DE {edition}",
        start=start,
        end=_parse_iso(dates["end_iso"], "end_iso"),
        venue=location["venue"],
    )


@cache
def load_brand() -> Brand:
    raw = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))
    branding = yaml.safe_load(BRANDING_PATH.read_text(encoding="utf-8"))
    brand = Brand(raw=raw, event=_load_event(branding, raw["edition"]))
    for key in raw["fonts"]:
        if not brand.font_path(key).is_file():
            raise BrandSpecError(f"font file missing: {brand.font_path(key)}")
    for color in raw["logo"]["files"]:
        if not brand.logo_path(color).is_file():
            raise BrandSpecError(f"logo file missing: {brand.logo_path(color)}")
    return brand
