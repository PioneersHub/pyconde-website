"""Aesthetic scoring of brand-compliant candidates.

Weights follow the art-direction brief: typography 35, composition 25,
hierarchy 20, colour 10, refinement 10. Typography and hierarchy are read
from the composition's geometry; balance and negative space from a small
render, the way a designer squints at a layout.

This is a filter for measurable faults and a tiebreaker between good
options. It is not a substitute for a designer's sign-off.
"""

import hashlib
from collections import deque
from dataclasses import dataclass, field

from PIL import Image, ImageChops

from social_cards.brand import Brand, contrast
from social_cards.composition import Composition, Raster, Rect
from social_cards.content import Card

WEIGHTS = {
    "typography": 35,
    "composition": 25,
    "hierarchy": 20,
    "color": 10,
    "refinement": 10,
}

# Typography
COMFORTABLE_LINES = 3
EXTRA_LINE_COST = 0.15
MIN_LINE_SCORE = 0.4
DISPLAY_CHARS = (10, 28)  # characters per display line that read well
# Share of the canvas the headline's ink box should cover to command the
# card; below it a headline reads as a caption lost in its field.
PRESENCE_TARGET = 0.07
# Composition
GRID = (16, 10)  # occupancy grid, columns × rows
INK_THRESHOLD = 24  # channel difference from the field that counts as ink
OPTICAL_CENTRE = (0.5, 0.48)
CENTROID_FREE_RADIUS = 0.08  # intended asymmetry costs nothing up to here
CENTROID_FALLOFF = 0.3
EMPTY_SHARE = (0.3, 0.72)  # below: crowded, above: sparse
SPARSE_FALLOFF = 0.2
CALM_FRAGMENTS = 3  # pieces of negative space before it reads as scattered
FRAGMENT_COST = 0.12
ALIGNMENT_SCORES = {1: 1.0, 2: 0.88, 3: 0.7}
ALIGNMENT_FALLBACK = 0.5
# Hierarchy
WEAK_HIERARCHY_SCORE = 0.3
STRONG_CONTRAST = 7.0
# Colour and refinement
FIELD_PREFERENCE_STEP = 0.12
REPEATED_FIELD = 0.65
MAX_DECORATIONS = 2
BUSY = 0.75
SAME_COMPOSITION = 0.6
SAME_STRATEGY = 0.85
RECENT_CARDS = 3


@dataclass
class Score:
    total: float
    parts: dict[str, float]
    notes: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        parts = " ".join(f"{k[:4]}={v:.2f}" for k, v in self.parts.items())
        return f"{self.total:5.1f} ({parts})"


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def _ink_mask(comp: Composition, brand: Brand, preview: Image.Image) -> Image.Image:
    """Binary mask of everything that is not the field colour. A photo panel
    differs from the field, so it counts as filled area."""
    field_rgb = Image.new("RGB", preview.size, brand.color(comp.field))
    diff = ImageChops.difference(preview, field_rgb).convert("L")
    return diff.point(lambda v: 255 if v > INK_THRESHOLD else 0)


def _components(empty: list[list[bool]]) -> int:
    rows, cols = len(empty), len(empty[0])
    seen = [[False] * cols for _ in range(rows)]
    count = 0
    for r in range(rows):
        for c in range(cols):
            if empty[r][c] and not seen[r][c]:
                count += 1
                queue = deque([(r, c)])
                seen[r][c] = True
                while queue:
                    y, x = queue.popleft()
                    for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                        if (
                            0 <= ny < rows
                            and 0 <= nx < cols
                            and empty[ny][nx]
                            and not seen[ny][nx]
                        ):
                            seen[ny][nx] = True
                            queue.append((ny, nx))
    return count


def _balance(mask: Image.Image) -> float:
    w, h = mask.size
    px = mask.load()
    total = mx = my = 0.0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if px[x, y]:
                total += 1
                mx += x
                my += y
    if not total:
        return 0.0
    off = (
        (mx / total / w - OPTICAL_CENTRE[0]) ** 2
        + (my / total / h - OPTICAL_CENTRE[1]) ** 2
    ) ** 0.5
    return _clamp(1 - max(0.0, off - CENTROID_FREE_RADIUS) / CENTROID_FALLOFF)


def _empty_cells(mask: Image.Image) -> list[list[bool]]:
    cols, rows = GRID
    cw, ch = mask.width / cols, mask.height / rows
    return [
        [
            mask.crop(
                (round(c * cw), round(r * ch), round((c + 1) * cw), round((r + 1) * ch))
            ).getbbox()
            is None
            for c in range(cols)
        ]
        for r in range(rows)
    ]


@dataclass
class Critic:
    """Scores the candidates for one card in one format."""

    brand: Brand
    card: Card
    # Largest headline any candidate of the same strategy achieved: size is
    # judged against what the layout allows, so a layout that gives room to
    # artwork or a photo is not marked down for its smaller headline.
    max_headline_size: dict[str, float]
    history: list[Composition]  # cards chosen before this one, same format

    def score(self, comp: Composition, preview: Image.Image) -> Score:
        notes: list[str] = []
        parts = {
            "typography": self.typography(comp, notes),
            "composition": self.composition(comp, preview, notes),
            "hierarchy": self.hierarchy(comp, notes),
            "color": self.color(comp),
            "refinement": self.refinement(comp),
        }
        return Score(
            total=sum(WEIGHTS[k] * v for k, v in parts.items()),
            parts=parts,
            notes=notes,
        )

    def typography(self, comp: Composition, notes: list[str]) -> float:
        hl = comp.text("headline").block
        size_use = hl.style.size / self.max_headline_size[comp.strategy]
        n = len(hl.lines)
        line_score = (
            1.0
            if n <= COMFORTABLE_LINES
            else max(MIN_LINE_SCORE, 1 - EXTRA_LINE_COST * (n - COMFORTABLE_LINES))
        )
        avg = sum(len(line.text) for line in hl.lines) / n
        lo, hi = DISPLAY_CHARS
        measure = (
            1.0
            if lo <= avg <= hi or n == 1
            else _clamp(1 - abs(avg - (lo + hi) / 2) / hi)
        )
        secondary = [
            t.block.quality for t in comp.texts if t.role in ("subline", "speaker")
        ]
        sec = sum(secondary) / len(secondary) if secondary else 1.0
        box = comp.text("headline").box
        presence = min(
            1.0, box.w * box.h / (comp.fmt.width * comp.fmt.height) / PRESENCE_TARGET
        )
        notes.extend(hl.issues)
        return _clamp(
            0.4 * hl.quality
            + 0.2 * size_use
            + 0.14 * presence
            + 0.1 * line_score
            + 0.08 * measure
            + 0.08 * sec
        )

    def composition(
        self, comp: Composition, preview: Image.Image, notes: list[str]
    ) -> float:
        mask = _ink_mask(comp, self.brand, preview)
        empty = _empty_cells(mask)
        empty_share = sum(map(sum, empty)) / (GRID[0] * GRID[1])
        low, high = EMPTY_SHARE
        if empty_share < low:
            space = empty_share / low
            notes.append("crowded")
        elif empty_share > high:
            space = _clamp(1 - (empty_share - high) / SPARSE_FALLOFF)
            notes.append("sparse")
        else:
            space = 1.0
        fragments = _components(empty)
        calm = _clamp(1 - FRAGMENT_COST * max(0, fragments - CALM_FRAGMENTS))
        if fragments > CALM_FRAGMENTS:
            notes.append(f"negative space broken into {fragments} pieces")
        lefts = {round(t.x / 4) for t in comp.texts if t.role != "cta"}
        align = ALIGNMENT_SCORES.get(len(lefts), ALIGNMENT_FALLBACK)
        return _clamp(0.32 * _balance(mask) + 0.3 * space + 0.18 * calm + 0.2 * align)

    def hierarchy(self, comp: Composition, notes: list[str]) -> float:
        hl = comp.text("headline")
        others = [t.size for t in comp.texts if t.role != "headline"]
        ratio = hl.size / max(others) if others else float("inf")
        spec = self.brand.raw["hierarchy"]
        lo, ideal = (
            spec["headline_to_secondary_min"],
            spec["headline_to_secondary_ideal"],
        )
        if ratio >= ideal:
            r = 1.0
        elif ratio >= lo:
            r = 0.65 + 0.35 * (ratio - lo) / (ideal - lo)
        else:
            r = WEAK_HIERARCHY_SCORE
            notes.append(f"weak hierarchy ({ratio:.2f}×)")
        c = contrast(self.brand.color(hl.color), self.brand.color(hl.ground))
        return _clamp(0.7 * r + 0.3 * min(1.0, c / STRONG_CONTRAST))

    def color(self, comp: Composition) -> float:
        fields = self.brand.category(self.card.category)["fields"]
        preference = 1.0 - FIELD_PREFERENCE_STEP * fields.index(comp.field)
        repeated = (
            self.history and self.history[-1].field == comp.field and len(fields) > 1
        )
        return _clamp(preference * (REPEATED_FIELD if repeated else 1.0))

    def refinement(self, comp: Composition) -> float:
        decorations = sum(
            1 for e in comp.elements if isinstance(e, Rect) and e.role == "spine"
        )
        decorations += sum(
            1 for e in comp.elements if isinstance(e, Raster) and e.kind == "python"
        )
        decorations += any(
            isinstance(e, Rect) and e.role == "brand_bar" for e in comp.elements
        )
        busy = 1.0 if decorations <= MAX_DECORATIONS else BUSY
        recent = self.history[-RECENT_CARDS:]
        if any(
            h.strategy == comp.strategy
            and h.params.get("logo") == comp.params.get("logo")
            for h in recent
        ):
            novelty = SAME_COMPOSITION
        elif any(h.strategy == comp.strategy for h in recent):
            novelty = SAME_STRATEGY
        else:
            novelty = 1.0
        # Card-specific tiebreak: equally good options differ between cards
        # but never between runs.
        jitter = (
            int(
                hashlib.sha256(f"{self.card.id}:{comp.key}".encode()).hexdigest()[:6],
                16,
            )
            / 0xFFFFFF
        )
        return _clamp(0.5 * busy + 0.4 * novelty + 0.1 * jitter)
