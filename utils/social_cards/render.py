"""Draw a Composition: SVG scene → PNG via resvg.

Text is emitted as glyph outlines from the shaped runs, the official logo
SVG is embedded verbatim inside a nested viewport (uniform scale only), and
rasters are embedded as data URIs. resvg renders with system fonts disabled,
so the result depends on nothing but the repository's own files.
"""

import base64
import hashlib
import io
import json
import re
from functools import cache
from pathlib import Path
from xml.sax.saxutils import escape

import resvg_py
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from social_cards.art import trimmed_png
from social_cards.brand import Brand
from social_cards.composition import Box, Composition, Logo, Raster, Rect, Text
from social_cards.sponsor_logo import load_sponsor_logo

# PNG text-chunk key under which a generated card records its content.
CARD_RECORD_KEY = "pyconde-social-card"
PIXELS_KEY = "pixels"
SVG_ROOT = re.compile(r"<svg\b[^>]*>(.*)</svg>", re.S)
VIEWBOX = re.compile(r'viewBox="([^"]+)"')


class RenderError(RuntimeError):
    pass


@cache
def logo_source(path: Path) -> tuple[str, tuple[float, float, float, float]]:
    """Inner markup and viewBox of an official logo file."""
    svg = path.read_text(encoding="utf-8")
    root = SVG_ROOT.search(svg)
    viewbox = VIEWBOX.search(svg)
    if not root or not viewbox:
        raise RenderError(f"{path} is not a plain SVG with a viewBox")
    x, y, w, h = (float(v) for v in viewbox.group(1).split())
    return root.group(1), (x, y, w, h)


def logo_aspect(brand: Brand, color: str) -> float:
    """Width / height of the official monogram."""
    _, (_, _, w, h) = logo_source(brand.logo_path(color))
    return w / h


def crop_photo(path: Path, box: Box, focus_y: float, scale: float) -> str:
    """Cover-crop a photo to the box aspect around a vertical focus point."""
    with Image.open(path) as src:
        im = src.convert("RGB")
    target = box.w / box.h
    w, h = im.size
    if w / h > target:
        cw = round(h * target)
        left = (w - cw) // 2
        im = im.crop((left, 0, left + cw, h))
    else:
        ch = round(w / target)
        top = round(min(max(focus_y * h - ch / 2, 0), h - ch))
        im = im.crop((0, top, w, top + ch))
    size = (round(box.w * scale), round(box.h * scale))
    im = im.resize(size, Image.Resampling.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=92, optimize=True)
    return f"data:image/jpeg;base64,{base64.b64encode(out.getvalue()).decode()}"


def _f(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _rect(e: Rect, brand: Brand) -> str:
    stroke = ""
    if e.stroke:
        # Stroke drawn inside the box, as a CSS border would be.
        half = e.stroke_width / 2
        b = e.box.inset(half)
        stroke = (
            f' stroke="{brand.color(e.stroke)}" stroke-width="{_f(e.stroke_width)}"'
        )
        return f'<rect x="{_f(b.x)}" y="{_f(b.y)}" width="{_f(b.w)}" height="{_f(b.h)}" fill="{brand.color(e.color)}"{stroke}/>'
    b = e.box
    return f'<rect x="{_f(b.x)}" y="{_f(b.y)}" width="{_f(b.w)}" height="{_f(b.h)}" fill="{brand.color(e.color)}"/>'


def _text(e: Text, brand: Brand) -> str:
    block = e.block
    style = block.style
    s = style.size / style.font.upem
    paths = []
    for run, offset, baseline in zip(
        block.lines, block.offsets, block.baselines, strict=True
    ):
        x0, y0 = e.x + offset, e.y + baseline
        for g in run.glyphs:
            d = style.font.glyph_path(g.gid)
            if d:
                paths.append(
                    f'<path transform="matrix({_f(s)} 0 0 {_f(-s)} {_f(x0 + g.x)} {_f(y0 - g.y)})" d="{d}"/>'
                )
    label = escape(block.text.replace("\n", " "))
    return f'<g fill="{brand.color(e.color)}" data-role="{e.role}" aria-label="{label}">{"".join(paths)}</g>'


def _logo(e: Logo, brand: Brand) -> str:
    inner, (vx, vy, vw, vh) = logo_source(brand.logo_path(e.color))
    b = e.box
    return (
        f'<svg x="{_f(b.x)}" y="{_f(b.y)}" width="{_f(b.w)}" height="{_f(b.h)}" '
        f'viewBox="{vx} {vy} {vw} {vh}" preserveAspectRatio="xMidYMid meet">{inner}</svg>'
    )


def _raster(e: Raster, scale: float, brand: Brand, field: str) -> str:
    b = e.box
    if e.kind == "photo":
        href = crop_photo(e.path, b, e.focus_y, scale)
        aspect = "none"
    elif e.kind == "sponsor_logo":
        png = load_sponsor_logo(e.path, brand, field).png
        href = f"data:image/png;base64,{base64.b64encode(png).decode()}"
        aspect = "xMidYMid meet"
    else:
        href = f"data:image/png;base64,{base64.b64encode(trimmed_png(e.path)).decode()}"
        aspect = "xMidYMid meet"
    return (
        f'<image x="{_f(b.x)}" y="{_f(b.y)}" width="{_f(b.w)}" height="{_f(b.h)}" '
        f'preserveAspectRatio="{aspect}" href="{href}"/>'
    )


def to_svg(comp: Composition, brand: Brand, scale: float = 1.0) -> str:
    fmt = comp.fmt
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt.width}" height="{fmt.height}" '
        f'viewBox="0 0 {fmt.width} {fmt.height}">',
        f'<rect width="{fmt.width}" height="{fmt.height}" fill="{brand.color(comp.field)}"/>',
    ]
    for e in comp.elements:
        if isinstance(e, Rect):
            parts.append(_rect(e, brand))
        elif isinstance(e, Text):
            parts.append(_text(e, brand))
        elif isinstance(e, Logo):
            parts.append(_logo(e, brand))
        elif isinstance(e, Raster):
            parts.append(_raster(e, scale, brand, comp.field))
    parts.append("</svg>")
    return "".join(parts)


def render(comp: Composition, brand: Brand, scale: float | None = None) -> Image.Image:
    """Rasterise at ``scale`` (default: the format's export scale)."""
    scale = comp.fmt.export_scale if scale is None else scale
    svg = to_svg(comp, brand, scale)
    try:
        png = resvg_py.svg_to_bytes(svg_string=svg, zoom=scale, skip_system_fonts=True)
    except ValueError as err:
        raise RenderError(f"resvg failed for {comp.key}: {err}") from err
    with Image.open(io.BytesIO(bytes(png))) as im:
        return im.convert("RGB")


def export_png(
    image: Image.Image, path: Path, record: dict[str, str] | None = None
) -> None:
    """Write the PNG; ``record`` (what the card shows) goes into a text
    chunk, so the file itself says what it was made from. A checksum of the
    pixels goes with it, so a hand edit is recognised even when the editing
    tool keeps the text chunk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    info = PngInfo()
    if record is not None:
        stamped = {**record, PIXELS_KEY: _pixel_digest(image)}
        info.add_text(
            CARD_RECORD_KEY, json.dumps(stamped, sort_keys=True, ensure_ascii=False)
        )
    image.save(path, "PNG", optimize=True, pnginfo=info)


def _pixel_digest(image: Image.Image) -> str:
    return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()


def read_card_record(path: Path) -> dict[str, str] | None:
    """The record of a card exactly as the generator drew it. None for any
    other PNG: one without a record, or one whose pixels were changed since."""
    with Image.open(path) as im:
        raw = im.text.get(CARD_RECORD_KEY)
        if not raw:
            return None
        record = json.loads(raw)
        if record.pop(PIXELS_KEY, None) != _pixel_digest(im):
            return None
    return record
