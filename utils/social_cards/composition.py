"""The vector scene a layout produces: what goes where, in which colour.

Layouts build a Composition; the validator checks it, the critic scores it
and the renderer draws it. Every element keeps its semantic role so brand
rules can be checked on intent ("headline on blue") rather than on pixels.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from social_cards.brand import Format
from social_cards.typeset import TextBlock

# How far above the cap line (in em) ink may reach and still count as
# aligned: IBM Plex ascenders and overshoots stay below 0.06 em, accents
# on capitals reach about 0.2 em.
ASCENDER_ALLOWANCE = 0.1


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    def intersects(self, other: "Box", gap: float = 0.0) -> bool:
        return not (
            self.right + gap <= other.x
            or other.right + gap <= self.x
            or self.bottom + gap <= other.y
            or other.bottom + gap <= self.y
        )

    def inset(self, d: float) -> "Box":
        return Box(self.x + d, self.y + d, self.w - 2 * d, self.h - 2 * d)

    def grow(self, d: float) -> "Box":
        return self.inset(-d)


@dataclass(frozen=True)
class Rect:
    """Flat colour area: field, panel, spine, brand-bar segment, CTA plate."""

    box: Box
    color: str
    role: str
    stroke: str | None = None
    stroke_width: float = 0.0


@dataclass(frozen=True)
class Text:
    block: TextBlock
    x: float  # optical left edge
    y: float  # cap height of the first line
    color: str
    role: str
    ground: str  # field colour under the text
    # Lines of one typographic unit set as separate runs (e.g. the bold
    # event name over the event facts); they may sit closer than the
    # minimum gap between unrelated elements.
    group: str | None = None

    @property
    def layout_box(self) -> Box:
        """Ink box with the last line ending on its baseline: descenders may
        hang into a margin, as in any typeset page."""
        b = self.box
        # Round letters and ascenders rise above the cap line by design;
        # only accents reach further and count against the top edge.
        top = self.y if self.y - b.y <= ASCENDER_ALLOWANCE * self.size else b.y
        return Box(b.x, top, b.w, self.y + self.block.height - top)

    @property
    def box(self) -> Box:
        """Ink box: cap top to the deepest descender, accents included."""
        style = self.block.style
        scale = style.size / style.font.upem
        top = self.y
        first = self.block.lines[0]
        for g in first.glyphs:
            bounds = style.font.glyph_bounds(g.gid)
            if bounds:
                top = min(top, self.y + style.cap_height - bounds[3] * scale)
        return Box(
            self.x,
            top,
            self.block.width,
            self.y + self.block.height + self.block.descent - top,
        )

    @property
    def size(self) -> float:
        return self.block.style.size


@dataclass(frozen=True)
class Logo:
    color: str  # key into brand logo files
    box: Box


@dataclass(frozen=True)
class Raster:
    path: Path
    box: Box
    kind: str  # "python" | "photo" | "sponsor_logo"
    focus_y: float = 0.5
    # Body colours of a python illustration (palette keys), for validation.
    colors: tuple[str, ...] = ()


Element = Rect | Text | Logo | Raster


@dataclass
class Composition:
    fmt: Format
    field: str
    strategy: str
    params: dict[str, Any]
    elements: list[Element] = field(default_factory=list)

    @property
    def texts(self) -> list[Text]:
        return [e for e in self.elements if isinstance(e, Text)]

    @property
    def logos(self) -> list[Logo]:
        return [e for e in self.elements if isinstance(e, Logo)]

    @property
    def rasters(self) -> list[Raster]:
        return [e for e in self.elements if isinstance(e, Raster)]

    @property
    def rects(self) -> list[Rect]:
        return [e for e in self.elements if isinstance(e, Rect)]

    def text(self, role: str) -> Text | None:
        return next((t for t in self.texts if t.role == role), None)

    @property
    def key(self) -> str:
        """Stable identity of a candidate, for de-duplication and logs."""
        params = ",".join(f"{k}={v}" for k, v in sorted(self.params.items()))
        return f"{self.strategy}[{params}]"
