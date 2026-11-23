"""Sponsor logos for thank-you cards: loaded once, checked, trimmed.

A sponsor's SVG is never embedded in the card's SVG: its ids and class
names would collide with ours. It is rendered on its own by resvg (system
fonts disabled, as for every card) and placed as a trimmed PNG, in its own
colours and proportions. A logo the renderer cannot draw faithfully — text
set in a font, an opaque background, too little contrast with the card — is
an error, never a silent substitute.
"""

import io
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import resvg_py
from PIL import Image

from social_cards.brand import Brand, contrast

LIVE_TEXT = re.compile(r"<text\b|@font-face")
OPAQUE = 250  # alpha from which a pixel counts as covered
VISIBLE = 128  # alpha from which a pixel counts as part of the logo


class SponsorLogoError(ValueError):
    """The logo file cannot be shown faithfully on a card."""


@dataclass(frozen=True)
class SponsorLogo:
    path: Path
    png: bytes  # trimmed to the visible logo
    width: int
    height: int
    rasterised: bool  # True for a raster source, which limits enlargement

    @property
    def aspect(self) -> float:
        return self.width / self.height


def _render_svg(path: Path, width: int) -> Image.Image:
    svg = path.read_text(encoding="utf-8")
    if LIVE_TEXT.search(svg):
        raise SponsorLogoError(
            f"{path.name} sets text in a font the card renderer does not load; "
            "it needs an SVG with outlined text, or a transparent PNG"
        )
    try:
        png = resvg_py.svg_to_bytes(svg_string=svg, width=width, skip_system_fonts=True)
    except ValueError as err:
        raise SponsorLogoError(
            f"{path.name} cannot be rendered ({err}); it needs an SVG with a "
            "viewBox, or a transparent PNG"
        ) from None
    with Image.open(io.BytesIO(bytes(png))) as im:
        return im.convert("RGBA")


def _check_transparent(path: Path, im: Image.Image) -> None:
    """A logo with its own opaque background would show as a box."""
    alpha = im.getchannel("A")
    w, h = im.size
    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    if all(alpha.getpixel(c) >= OPAQUE for c in corners):
        raise SponsorLogoError(
            f"{path.name} has an opaque background; it needs a transparent PNG or an SVG"
        )


def _check_visible(path: Path, im: Image.Image, brand: Brand, field: str) -> None:
    """Enough of the logo must stand out from the card's background."""
    spec = brand.raw["sponsor_logo"]
    ground = brand.color(field)
    small = im.copy()
    small.thumbnail((200, 200))
    pixels = [p for p in small.get_flattened_data() if p[3] >= VISIBLE]  # RGBA tuples
    if not pixels:
        raise SponsorLogoError(f"{path.name} has no visible pixels")
    standing_out = sum(
        1
        for r, g, b, _ in pixels
        if contrast(f"#{r:02x}{g:02x}{b:02x}", ground) >= spec["min_ink_contrast"]
    )
    if standing_out / len(pixels) < spec["min_ink_share"]:
        raise SponsorLogoError(
            f"{path.name} is too light to read on the {field} background; "
            "it needs a version for light backgrounds"
        )


@cache
def load_sponsor_logo(path: Path, brand: Brand, field: str) -> SponsorLogo:
    """The logo ready to place on a `field` card, or SponsorLogoError."""
    if not path.is_file():
        raise SponsorLogoError(f"sponsor logo not found: {path}")
    if path.suffix.lower() == ".svg":
        im = _render_svg(path, brand.raw["sponsor_logo"]["render_width"])
        rasterised = False
    else:
        with Image.open(path) as src:
            im = src.convert("RGBA")
        _check_transparent(path, im)
        rasterised = True
    bbox = im.getchannel("A").point(lambda a: 255 if a >= VISIBLE else 0).getbbox()
    if bbox is None:
        raise SponsorLogoError(f"{path.name} has no visible pixels")
    im = im.crop(bbox)
    _check_visible(path, im, brand, field)
    out = io.BytesIO()
    im.save(out, "PNG", optimize=True)
    return SponsorLogo(path, out.getvalue(), im.width, im.height, rasterised)
