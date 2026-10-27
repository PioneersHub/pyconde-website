"""Shaped text measurement and glyph outlines.

HarfBuzz shapes every run (kerning, ligatures, marks), fontTools supplies
the outlines and true ink bounds. Cards are drawn from these outlines, so the
width the typesetter measures is exactly the width that gets rendered — and
no renderer can ever fall back to a different font.
"""

from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

FEATURES = {"kern": True, "liga": True, "calt": True}


@dataclass(frozen=True)
class GlyphPlacement:
    gid: int
    x: float  # px from the run origin
    y: float  # px, positive = up (font convention)


@dataclass(frozen=True)
class ShapedRun:
    """One line of shaped text at a given size, origin on the baseline."""

    font: "Font"
    text: str
    size: float
    glyphs: tuple[GlyphPlacement, ...]
    advance: float

    @property
    def scale(self) -> float:
        return self.size / self.font.upem

    @cached_property
    def ink_left(self) -> float:
        """Distance from the origin to the first inked pixel (side bearing)."""
        for g in self.glyphs:
            bounds = self.font.glyph_bounds(g.gid)
            if bounds:
                return g.x + bounds[0] * self.scale
        return 0.0

    @cached_property
    def ink_right(self) -> float:
        for g in reversed(self.glyphs):
            bounds = self.font.glyph_bounds(g.gid)
            if bounds:
                return g.x + bounds[2] * self.scale
        return 0.0

    @property
    def ink_width(self) -> float:
        return self.ink_right - self.ink_left


class Font:
    def __init__(self, path: Path):
        self.path = path
        blob = hb.Blob.from_file_path(str(path))
        self._hb_font = hb.Font(hb.Face(blob))
        self._tt = TTFont(path)
        self._glyph_set = self._tt.getGlyphSet()
        self._glyph_order = self._tt.getGlyphOrder()
        self.upem: int = self._tt["head"].unitsPerEm
        os2 = self._tt["OS/2"]
        self.cap_height: int = os2.sCapHeight
        self.descender: int = self._tt["hhea"].descent

    def __repr__(self) -> str:
        return f"Font({self.path.name})"

    @cache  # noqa: B019 — fonts live for the whole process
    def shape(self, text: str, size: float, tracking: float = 0.0) -> ShapedRun:
        """Shape ``text`` at ``size`` px; ``tracking`` is in em."""
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self._hb_font, buf, FEATURES)
        scale = size / self.upem
        track = tracking * size
        x = 0.0
        glyphs = []
        infos, positions = buf.glyph_infos, buf.glyph_positions
        for i, (info, pos) in enumerate(zip(infos, positions, strict=True)):
            glyphs.append(
                GlyphPlacement(
                    info.codepoint, x + pos.x_offset * scale, pos.y_offset * scale
                )
            )
            x += pos.x_advance * scale
            if i < len(infos) - 1:
                x += track
        return ShapedRun(self, text, size, tuple(glyphs), x)

    def has_glyphs_for(self, text: str) -> bool:
        cmap = self._tt.getBestCmap()
        return all(ord(ch) in cmap for ch in text if not ch.isspace())

    @cache  # noqa: B019
    def glyph_bounds(self, gid: int) -> tuple[int, int, int, int] | None:
        """(xMin, yMin, xMax, yMax) in font units, None for empty glyphs."""
        glyph = self._tt["glyf"][self._glyph_order[gid]]
        if glyph.numberOfContours == 0:
            return None
        return glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax

    @cache  # noqa: B019
    def glyph_path(self, gid: int) -> str:
        """SVG path data in font units (y up)."""
        pen = SVGPathPen(self._glyph_set)
        self._glyph_set[self._glyph_order[gid]].draw(pen)
        return pen.getCommands()


@cache
def load_font(path: Path) -> Font:
    return Font(path)
