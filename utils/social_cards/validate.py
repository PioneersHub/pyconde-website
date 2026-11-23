"""Hard checks: a candidate with any violation is never published.

Brand fidelity is a constraint, not a score. These checks run on the vector
composition, where intent is explicit (this text is the headline, on blue,
in IBM Plex Sans Bold), so they are exact rather than inferred from pixels.
"""

import re
from dataclasses import dataclass
from itertools import combinations

from PIL import Image

from social_cards.brand import REPO_ROOT, Brand, contrast
from social_cards.composition import Composition, Logo, Raster, Rect, Text
from social_cards.content import Card
from social_cards.render import logo_aspect

CONTENT_ROLES = ("cta_plate",)
LOGO_ASPECT_TOLERANCE = 0.002


@dataclass(frozen=True)
class Violation:
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.detail}"


def _normalise(text: str) -> str:
    return " ".join(text.split())


def _allowed_text_colors(brand: Brand, ground: str) -> set[str]:
    if ground in brand.raw["fields"]:
        f = brand.field(ground)
        return {f["text"], f["accent"]}
    cta = brand.raw["cta"]
    plates = {
        cta["fill"]: cta["text"],
        cta["on_matching_field"]["fill"]: cta["on_matching_field"]["text"],
    }
    return {plates[ground]} if ground in plates else set()


def _check_field(comp: Composition, brand: Brand, card: Card) -> list[Violation]:
    if comp.field not in brand.raw["fields"]:
        return [Violation("field", f"'{comp.field}' is not an approved card field")]
    if comp.field not in brand.category(card.category)["fields"]:
        return [
            Violation("field", f"'{comp.field}' is not permitted for {card.category}")
        ]
    return []


def _check_rects(comp: Composition, brand: Brand) -> list[Violation]:
    out = [
        Violation("palette", f"{e.role} uses unapproved colour '{color}'")
        for e in comp.rects
        for color in (e.color, e.stroke)
        if color and color not in brand.palette
    ]
    bar_rects = [r.color for r in comp.rects if r.role == "brand_bar"]
    if bar_rects:
        bar = brand.raw["brand_bar"]
        if bar_rects != bar["order"]:
            out.append(
                Violation(
                    "brand-bar", f"colour order {bar_rects} differs from {bar['order']}"
                )
            )
        if comp.field not in bar["fields"]:
            out.append(
                Violation("brand-bar", f"brand bar not permitted on {comp.field}")
            )
    return out


def _check_text_colors(comp: Composition, brand: Brand) -> list[Violation]:
    out = []
    palette = brand.palette
    forbidden = {tuple(p) for p in brand.raw["forbidden_pairs"]}
    for t in comp.texts:
        if t.color not in palette:
            out.append(
                Violation("palette", f"{t.role} uses unapproved colour '{t.color}'")
            )
            continue
        if t.color not in _allowed_text_colors(brand, t.ground):
            out.append(
                Violation(
                    "color-pair",
                    f"{t.role}: {t.color} text is not approved on {t.ground}",
                )
            )
        if (t.ground, t.color) in forbidden:
            out.append(
                Violation(
                    "color-pair",
                    f"{t.role}: {t.color} on {t.ground} is a forbidden pair",
                )
            )
        ratio = contrast(palette[t.color], palette[t.ground])
        if ratio < brand.raw["min_text_contrast"]:
            out.append(
                Violation(
                    "contrast",
                    f"{t.role}: {ratio:.2f}:1 is below {brand.raw['min_text_contrast']}:1",
                )
            )
    return out


def check_colors(comp: Composition, brand: Brand, card: Card) -> list[Violation]:
    out = (
        _check_field(comp, brand, card)
        + _check_rects(comp, brand)
        + _check_text_colors(comp, brand)
    )
    out += [
        Violation(
            "python-color",
            f"{r.path.name} has a {comp.field} segment on a {comp.field} field",
        )
        for r in comp.rasters
        if r.kind == "python" and comp.field in r.colors
    ]
    return out


def check_typography(comp: Composition, brand: Brand) -> list[Violation]:
    out = []
    approved = {REPO_ROOT / p for p in brand.raw["fonts"].values()}
    floor = comp.fmt.px(brand.raw["min_text_px"])
    for t in comp.texts:
        font = t.block.style.font
        if font.path not in approved:
            out.append(
                Violation("font", f"{t.role} uses unapproved font {font.path.name}")
            )
        if not font.has_glyphs_for(t.block.text):
            out.append(
                Violation(
                    "font",
                    f"{t.role}: {font.path.name} lacks glyphs for {t.block.text!r}",
                )
            )
        if t.size < floor - 0.01:
            out.append(
                Violation(
                    "tiny-text", f"{t.role} at {t.size:.1f}px is below {floor:.1f}px"
                )
            )
    hl = comp.text("headline")
    if hl is None:
        out.append(Violation("hierarchy", "no headline"))
    elif "single-word last line" in hl.block.issues:
        out.append(
            Violation(
                "orphan", f"headline ends on a single word: {hl.block.lines[-1].text!r}"
            )
        )
    return out


def check_logo(comp: Composition, brand: Brand) -> list[Violation]:
    out = []
    if len(comp.logos) != 1:
        return [
            Violation("logo", f"expected exactly one logo, found {len(comp.logos)}")
        ]
    lg: Logo = comp.logos[0]
    if lg.color not in brand.raw["logo"]["files"]:
        out.append(Violation("logo", f"'{lg.color}' is not an official logo file"))
        return out
    if lg.color not in brand.field(comp.field)["logo"]:
        out.append(
            Violation("logo", f"{lg.color} logo is not approved on {comp.field}")
        )
    aspect = lg.box.w / lg.box.h
    official = logo_aspect(brand, lg.color)
    if abs(aspect / official - 1) > LOGO_ASPECT_TOLERANCE:
        out.append(
            Violation(
                "logo-distortion",
                f"aspect {aspect:.4f} differs from official {official:.4f}",
            )
        )
    min_h = comp.fmt.px(brand.raw["logo"]["min_height"])
    if lg.box.h < min_h - 0.5:
        out.append(
            Violation("logo", f"logo {lg.box.h:.0f}px tall, minimum {min_h:.0f}px")
        )
    zone = lg.box.grow(lg.box.w * brand.raw["logo"]["clear_space_ratio"])
    for e in comp.elements:
        if e is lg or (isinstance(e, Rect) and e.role == "brand_bar"):
            continue
        if zone.intersects(e.box):
            role = getattr(e, "role", getattr(e, "kind", "element"))
            out.append(
                Violation("logo-clear-space", f"{role} inside the logo clear space")
            )
    return out


def check_photos(comp: Composition, brand: Brand) -> list[Violation]:
    out = []
    limit = brand.raw["photo"]["max_upscale"]
    for r in comp.rasters:
        if r.kind != "photo":
            continue
        with Image.open(r.path) as im:
            w, h = im.size
        # Cover crop: the limiting side is the one the box fills completely.
        need = max(r.box.w / w, r.box.h / h) * comp.fmt.export_scale
        if need > limit:
            out.append(
                Violation(
                    "photo-resolution",
                    f"{r.path.name} ({w}×{h}) would be enlarged {need:.1f}×",
                )
            )
    return out


def check_geometry(comp: Composition) -> list[Violation]:
    out = []
    fmt = comp.fmt
    m = fmt.margin
    safe_top, safe_bottom = m + fmt.safe_top, fmt.height - m - fmt.safe_bottom
    tolerance = 1.0
    for e in comp.elements:
        if isinstance(e, Text | Logo) or (
            isinstance(e, Rect) and e.role in CONTENT_ROLES
        ):
            b = e.layout_box if isinstance(e, Text) else e.box
            if (
                b.x < m - tolerance
                or b.right > fmt.width - m + tolerance
                or b.y < safe_top - tolerance
                or b.bottom > safe_bottom + tolerance
            ):
                role = getattr(e, "role", "logo")
                out.append(Violation("safe-area", f"{role} leaves the safe area"))
    # Collisions between content elements (the CTA label sits on its plate).
    content = [
        e
        for e in comp.elements
        if isinstance(e, Text | Logo | Raster)
        or (isinstance(e, Rect) and e.role in ("cta_plate", "spine"))
    ]
    gap = fmt.unit * 0.75
    for a, b in combinations(content, 2):
        roles = {getattr(a, "role", None), getattr(b, "role", None)}
        if roles == {"cta", "cta_plate"}:
            continue
        if (
            isinstance(a, Text)
            and isinstance(b, Text)
            and a.group
            and a.group == b.group
        ):
            continue
        if isinstance(a, Rect) and isinstance(b, Rect):
            continue
        if a.box.intersects(b.box, gap):
            ra = getattr(a, "role", getattr(a, "kind", "logo"))
            rb = getattr(b, "role", getattr(b, "kind", "logo"))
            out.append(Violation("collision", f"{ra} and {rb} touch or overlap"))
    return out


def check_copy(comp: Composition, brand: Brand, card: Card) -> list[Violation]:
    out = []
    texts = {t.role: _normalise(t.block.text.replace("\n", " ")) for t in comp.texts}
    everything = " ".join(texts.values())
    for rule in brand.raw["forbidden_terms"]:
        if re.search(rule["pattern"], everything):
            out.append(Violation("copy", rule["reason"]))
    for year in re.findall(r"PyCon DE (\d{4})", everything):
        if int(year) != brand.raw["edition"]:
            out.append(
                Violation(
                    "edition", f"'PyCon DE {year}' on a {brand.raw['edition']} card"
                )
            )
    expected = {
        "headline": card.headline,
        "subline": card.subline,
        "speaker": card.speaker_line or None,
        "event_name": brand.event.name,
    }
    for role, text in expected.items():
        if text is not None and role in texts and texts[role] != _normalise(text):
            out.append(
                Violation(
                    "content-altered",
                    f"{role} reads {texts[role]!r}, expected {text!r}",
                )
            )
    if "headline" not in texts:
        out.append(Violation("content-missing", "headline not on the card"))
    if card.speakers and "speaker" not in texts and card.speaker_line != card.headline:
        out.append(Violation("content-missing", "speakers not on the card"))
    if card.subline and "subline" not in texts:
        out.append(Violation("content-missing", "subline not on the card"))
    if card.image and not any(r.kind == "photo" for r in comp.rasters):
        out.append(Violation("content-missing", "the card's photo is not used"))
    if card.cta and "cta" not in texts:
        out.append(Violation("content-missing", "call to action not on the card"))
    facts = texts.get("event_facts", "")
    expected_dates = brand.event_dates(card.lang, card.event)
    if expected_dates not in facts or brand.event.venue not in facts:
        out.append(
            Violation(
                "event-facts", f"event facts {facts!r} do not match branding.yaml"
            )
        )
    return out


def validate(comp: Composition, brand: Brand, card: Card) -> list[Violation]:
    return [
        *check_colors(comp, brand, card),
        *check_typography(comp, brand),
        *check_logo(comp, brand),
        *check_photos(comp, brand),
        *check_geometry(comp),
        *check_copy(comp, brand, card),
    ]
