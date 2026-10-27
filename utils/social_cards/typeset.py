"""Typesetting: line breaking, size search and optical alignment.

Headlines are short, so the breaker enumerates every break set that fits the
measure instead of filling lines greedily, and scores each one the way a
typographer would judge it: an even rag, no weak word at a line end, a last
line that carries weight, natural pauses after colons and dashes. Size is
searched in the brand's discrete steps; a smaller step is only taken when no
arrangement at the larger one is good enough.
"""

import re
from dataclasses import dataclass, field
from functools import cached_property

from social_cards.brand import Brand, Format
from social_cards.fonts import Font, ShapedRun, load_font

OPENING_PUNCTUATION = "“„\"'‚‘«»([‹›"
# A version number, dash or colon belongs to the word before it.
GLUE_TO_PREVIOUS = re.compile(r"^(v?\d[\w.+-]*|[–—:·/|])$")
# A count binds to a short unit or noun after it: '40 TB', '3 Tage'.
COUNT = re.compile(r"^\d[\d,.]*\+?%?$")
MAX_UNIT_LEN = 5

ACCEPTABLE_QUALITY = 0.72

# Break-scoring weights. Quality starts at 1 and each fault subtracts.
RAG_WEIGHT = 2.2
ORPHAN_PENALTY = 0.9  # single-word last line
# A single last word is only an orphan when it is short against the line
# above: 'Rust for Python / Developers' is a sound break.
ORPHAN_RATIO = 0.6
STUB_PENALTY = 0.6  # last line below min_last_line_ratio
SHORT_LAST_RATIO = 0.5  # below this the last line starts to look thin
SHORT_LAST_WEIGHT = 0.6
TOP_LIGHT_RATIO = 0.6  # last line dwarfs the one above it
TOP_LIGHT_PENALTY = 0.15
WEAK_END_PENALTY = 0.35
STRONG_END_BONUS = 0.12
SPLIT_PHRASE_PENALTY = 0.2
LINE_COST = 0.01  # ties go to fewer lines
SENTENCE_CASE_MAX_CAPITALS = 0.6


@dataclass(frozen=True)
class TextStyle:
    font: Font
    size: float
    leading: float
    tracking: float
    uppercase: bool = False

    @property
    def line_height(self) -> float:
        return self.size * self.leading

    @property
    def cap_height(self) -> float:
        return self.font.cap_height * self.size / self.font.upem

    @property
    def descent(self) -> float:
        return -self.font.descender * self.size / self.font.upem

    def shape(self, text: str) -> ShapedRun:
        if self.uppercase:
            text = text.upper()
        return self.font.shape(text, round(self.size, 3), self.tracking)


@dataclass(frozen=True)
class TextBlock:
    """A set line block. Coordinates: x at the optical left edge, y = 0 at the
    cap height of the first line, growing downwards."""

    lines: tuple[ShapedRun, ...]
    style: TextStyle
    quality: float = 1.0
    issues: tuple[str, ...] = field(default=())

    @cached_property
    def offsets(self) -> tuple[float, ...]:
        """Per-line x shift so ink (not the advance box) aligns at x = 0.
        Opening punctuation hangs into the margin."""
        result = []
        for run in self.lines:
            shift = -run.ink_left
            if run.text[:1] in OPENING_PUNCTUATION and len(run.glyphs) > 1:
                shift = -run.glyphs[1].x
            result.append(shift)
        return tuple(result)

    @cached_property
    def width(self) -> float:
        return max(
            run.ink_right + off
            for run, off in zip(self.lines, self.offsets, strict=True)
        )

    @property
    def baselines(self) -> tuple[float, ...]:
        cap, lh = self.style.cap_height, self.style.line_height
        return tuple(cap + i * lh for i in range(len(self.lines)))

    @property
    def height(self) -> float:
        """Cap top of the first line to the baseline of the last."""
        return self.baselines[-1]

    @property
    def descent(self) -> float:
        return self.style.descent

    @property
    def text(self) -> str:
        return "\n".join(run.text for run in self.lines)


def style_for(
    brand: Brand, fmt: Format, role: str, size_ref: float | None = None
) -> TextStyle:
    """Resolve a role at one size. ``size_ref`` is a 1200-px reference size."""
    spec = brand.role(role)
    ref = size_ref if size_ref is not None else spec["size"]
    return TextStyle(
        font=load_font(brand.font_path(spec["font"])),
        size=fmt.px(ref),
        leading=_interpolate(spec["leading"], ref),
        tracking=_interpolate(spec["tracking"], ref),
        uppercase=spec.get("uppercase", False),
    )


def role_sizes(brand: Brand, role: str) -> list[float]:
    spec = brand.role(role)
    return list(spec.get("sizes", [spec.get("size")]))


def _interpolate(value: float | dict, size: float) -> float:
    """Leading/tracking may vary with size: linear between two anchors."""
    if not isinstance(value, dict):
        return value
    big, small = value["large"], value["small"]
    if size >= big:
        return value["at_large"]
    if size <= small:
        return value["at_small"]
    t = (size - small) / (big - small)
    return value["at_small"] + t * (value["at_large"] - value["at_small"])


def tokenize(text: str) -> list[str]:
    """Split into unbreakable units: a version number stays with the word
    before it ('Python 3.14'), a dash or colon never starts a line."""
    units: list[str] = []
    for word in text.split():
        previous = units[-1].split()[-1] if units else ""
        if units and (
            GLUE_TO_PREVIOUS.match(word)
            or (COUNT.match(previous) and len(word.strip(",.;:")) <= MAX_UNIT_LEN)
        ):
            units[-1] = f"{units[-1]} {word}"
        else:
            units.append(word)
    return units


@dataclass(frozen=True)
class Frame:
    """The space a block may take: measure, height (cap top to last
    baseline) and line count."""

    width: float
    height: float | None = None
    lines: int = 1


@dataclass
class _Breaker:
    units: list[str]
    style: TextStyle
    max_width: float
    weak: frozenset[str]
    strong: tuple[str, ...]
    min_last_ratio: float

    def __post_init__(self):
        self._width_cache: dict[tuple[int, int], float] = {}

    def width(self, i: int, j: int) -> float:
        key = (i, j)
        if key not in self._width_cache:
            self._width_cache[key] = self.style.shape(
                " ".join(self.units[i:j])
            ).ink_width
        return self._width_cache[key]

    def partitions(self, max_lines: int):
        n = len(self.units)

        def walk(start: int, lines_left: int, acc: list[int]):
            if start == n:
                yield tuple(acc)
                return
            if lines_left == 0:
                return
            for end in range(start + 1, n + 1):
                if self.width(start, end) > self.max_width:
                    break
                acc.append(end)
                yield from walk(end, lines_left - 1, acc)
                acc.pop()

        yield from walk(0, max_lines, [])

    def score(self, breaks: tuple[int, ...]) -> tuple[float, list[str]]:
        spans = list(zip((0, *breaks[:-1]), breaks, strict=True))
        widths = [self.width(i, j) for i, j in spans]
        issues: list[str] = []
        k = len(spans)
        if k == 1:
            return 1.0, issues
        longest = max(widths)
        # Rag: non-final lines should be close to the longest one.
        penalty = (
            RAG_WEIGHT
            * sum(((longest - w) / longest) ** 2 for w in widths[:-1])
            / (k - 1)
        )
        penalty += self._last_line(spans, widths, longest, issues)
        for _, j in spans[:-1]:
            penalty += self._line_end(j, issues)
        return max(0.0, min(1.0, 1.0 - penalty)), issues

    def _last_line(
        self,
        spans: list[tuple[int, int]],
        widths: list[float],
        longest: float,
        issues: list[str],
    ) -> float:
        """A short single word reads as an orphan; a stub looks unplanned."""
        penalty = 0.0
        last_i, last_j = spans[-1]
        ratio = widths[-1] / longest
        single = len(" ".join(self.units[last_i:last_j]).split()) == 1
        if single and ratio < ORPHAN_RATIO and len(self.units) > len(spans):
            penalty += ORPHAN_PENALTY
            issues.append("single-word last line")
        if ratio < self.min_last_ratio:
            penalty += STUB_PENALTY
            issues.append("short last line")
        elif ratio < SHORT_LAST_RATIO:
            penalty += (SHORT_LAST_RATIO - ratio) * SHORT_LAST_WEIGHT
        if widths[-1] >= longest and widths[-2] < widths[-1] * TOP_LIGHT_RATIO:
            penalty += TOP_LIGHT_PENALTY
        return penalty

    def _line_end(self, j: int, issues: list[str]) -> float:
        last_word = self.units[j - 1].split()[-1]
        bare = last_word.strip(",.;:!?").lower()
        if bare in self.weak or last_word in self.weak:
            issues.append(f"weak line ending '{last_word}'")
            return WEAK_END_PENALTY
        if last_word.endswith(self.strong):
            return -STRONG_END_BONUS
        if (
            self.sentence_case
            and _capitalised(last_word)
            and j < len(self.units)
            and _capitalised(self.units[j])
        ):
            # 'Data | Science' in a sentence-case title splits a name.
            issues.append(f"split phrase '{last_word} {self.units[j]}'")
            return SPLIT_PHRASE_PENALTY
        return 0.0

    @cached_property
    def sentence_case(self) -> bool:
        """Title Case capitalises every word, so capitals carry no phrase
        information there; in sentence case they mark names."""
        words = [w for unit in self.units for w in unit.split() if w[:1].isalpha()]
        return (
            bool(words)
            and sum(_capitalised(w) for w in words) / len(words)
            < SENTENCE_CASE_MAX_CAPITALS
        )


def _capitalised(word: str) -> bool:
    return word[:1].isupper()


def set_block(
    brand: Brand, content: str | list[str], style: TextStyle, frame: Frame
) -> TextBlock | None:
    """Best arrangement at one style, or None if nothing fits the frame.

    ``content`` is text, or a list of units that must never break inside
    (speaker names)."""
    units = tokenize(content) if isinstance(content, str) else list(content)
    if not units:
        raise ValueError("cannot typeset empty text")
    rules = brand.raw["line_breaking"]
    breaker = _Breaker(
        units=units,
        style=style,
        max_width=frame.width,
        weak=frozenset(w.lower() for w in rules["weak_line_endings"]),
        strong=tuple(rules["strong_line_endings"]),
        min_last_ratio=rules["min_last_line_ratio"],
    )
    best: tuple[float, tuple[int, ...], list[str]] | None = None
    for breaks in breaker.partitions(frame.lines):
        k = len(breaks)
        if (
            frame.height is not None
            and style.cap_height + (k - 1) * style.line_height > frame.height
        ):
            continue
        quality, issues = breaker.score(breaks)
        quality -= LINE_COST * k
        if best is None or quality > best[0]:
            best = (quality, breaks, issues)
    if best is None:
        return None
    quality, breaks, issues = best
    starts = (0, *breaks[:-1])
    lines = tuple(
        style.shape(" ".join(units[i:j])) for i, j in zip(starts, breaks, strict=True)
    )
    return TextBlock(
        lines=lines, style=style, quality=max(0.0, quality), issues=tuple(issues)
    )


def set_best(
    brand: Brand, fmt: Format, role: str, content: str | list[str], frame: Frame
) -> list[TextBlock]:
    """All arrangements across the role's size steps, best first.

    Sizes reaching ACCEPTABLE_QUALITY come first, largest first, then the
    rest, so a layout can trade size for shape when composition demands it.
    ``frame.lines`` of 0 means the role's own max_lines. Empty when nothing
    fits."""
    lines = frame.lines or brand.role(role).get("max_lines", 1)
    blocks = []
    for size in role_sizes(brand, role):
        style = style_for(brand, fmt, role, size)
        block = set_block(
            brand, content, style, Frame(frame.width, frame.height, lines)
        )
        if block is not None:
            blocks.append(block)
    good = [b for b in blocks if b.quality >= ACCEPTABLE_QUALITY]
    rest = [b for b in blocks if b.quality < ACCEPTABLE_QUALITY]
    return good + rest


def set_line(style: TextStyle, text: str, max_width: float) -> TextBlock | None:
    """Single unbroken line (labels, meta). None if it does not fit."""
    run = style.shape(text)
    if run.ink_width > max_width:
        return None
    return TextBlock(lines=(run,), style=style)
