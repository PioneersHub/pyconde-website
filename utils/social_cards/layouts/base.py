"""Shared grid and building blocks for all layout strategies.

Vertical rhythm is measured baseline-to-cap-top: the gap between two text
blocks is the distance from the last baseline of the upper block to the cap
height of the lower one. That is the space the eye perceives, independent of
font size, so a 'md' gap looks the same under a 48 px and a 116 px headline.
"""

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from typing import Any

from social_cards.brand import Brand, Format, contrast
from social_cards.composition import Box, Composition, Logo, Rect, Text
from social_cards.content import Analysis, Card
from social_cards.render import logo_aspect
from social_cards.typeset import (
    Frame,
    TextBlock,
    role_sizes,
    set_best,
    set_line,
    style_for,
)

# Headline measure as a share of the text column, tried during refinement.
MEASURES = (0.62, 0.72, 0.84, 1.0)


class DoesNotFitError(Exception):
    """The content cannot be set in this variant without breaking a rule."""


@dataclass
class Context:
    brand: Brand
    fmt: Format
    card: Card
    analysis: Analysis

    @property
    def u(self) -> float:
        return self.fmt.unit

    @cached_property
    def content(self) -> Box:
        f = self.fmt
        m = f.margin
        top = m + f.safe_top
        return Box(m, top, f.width - 2 * m, f.height - top - m - f.safe_bottom)

    def space(self, name: str) -> float:
        return self.brand.raw["spacing"][name] * self.u

    def deco(self, name: str) -> float:
        return self.brand.raw["decoration"][name] * self.u

    def text_color(self, field: str) -> str:
        return self.brand.field(field)["text"]

    def accent(self, field: str) -> str:
        return self.brand.field(field)["accent"]

    def pick(self, options: list[Any], count: int, salt: str) -> list[Any]:
        """Deterministic, card-specific choice of ``count`` options."""
        if not options:
            return []
        h = int(hashlib.sha256(f"{self.card.id}:{salt}".encode()).hexdigest()[:8], 16)
        start = h % len(options)
        rotated = options[start:] + options[:start]
        return rotated[:count]


class Strategy:
    name: str = ""

    def applicable(self, _ctx: Context) -> bool:
        return True

    def variants(self, ctx: Context, fields: list[str]) -> Iterator[dict[str, Any]]:
        raise NotImplementedError

    def neighbours(
        self, _ctx: Context, params: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        """Small adjustments of a good candidate, for the refinement pass."""
        for shift in (params.get("size_shift", 0) - 1, params.get("size_shift", 0) + 1):
            if shift >= 0:
                yield {**params, "size_shift": shift}
        for measure in MEASURES:
            if measure != params.get("measure"):
                yield {**params, "measure": measure}

    def build(self, ctx: Context, params: dict[str, Any]) -> Composition:
        raise NotImplementedError


# ── building blocks ──────────────────────────────────────────


def logo_box(
    ctx: Context, height: float, x: float, y: float, align_right: bool = False
) -> Box:
    min_h = ctx.fmt.px(ctx.brand.raw["logo"]["min_height"])
    if height < min_h - 0.5:
        raise DoesNotFitError(
            f"logo would be {height:.0f}px, below the {min_h:.0f}px minimum"
        )
    width = height * logo_aspect(ctx.brand, "white")
    return Box(x - width if align_right else x, y, width, height)


def logo(ctx: Context, field: str, box: Box, variant: int = 0) -> Logo:
    colors = ctx.brand.field(field)["logo"]
    return Logo(color=colors[variant % len(colors)], box=box)


def clear_space(ctx: Context, box: Box) -> float:
    return box.w * ctx.brand.raw["logo"]["clear_space_ratio"]


def logo_gap(ctx: Context, box: Box) -> float:
    """Distance from a text column to a logo beside it: the clear space is
    the legal minimum, a designer leaves more."""
    return max(clear_space(ctx, box), ctx.space("xl"))


def kicker(
    ctx: Context, field: str, x: float, y: float, max_width: float
) -> Text | None:
    text = ctx.card.kicker_text(ctx.brand)
    if not text:
        return None
    block = set_line(style_for(ctx.brand, ctx.fmt, "kicker"), text, max_width)
    if block is None:
        raise DoesNotFitError("kicker does not fit on one line")
    return Text(block, x, y, ctx.text_color(field), "kicker", field)


def event_lines(
    ctx: Context, field: str, x: float, max_width: float, last_baseline: float
) -> list[Text]:
    """'PyCon DE 2027' over 'dates · venue', bottom-aligned on ``last_baseline``.
    In a narrow column dates and venue take a line each, as on the site hero."""
    brand, fmt = ctx.brand, ctx.fmt
    name = set_line(style_for(brand, fmt, "meta_strong"), brand.event.name, max_width)
    dates, venue = brand.event_dates(ctx.card.lang), brand.event.venue
    style = style_for(brand, fmt, "meta")
    facts = set_line(style, f"{dates} · {venue}", max_width)
    if facts is None and all(
        style.shape(t).ink_width <= max_width for t in (dates, venue)
    ):
        facts = TextBlock(lines=(style.shape(dates), style.shape(venue)), style=style)
    if name is None or facts is None:
        raise DoesNotFitError("event facts do not fit")
    color = ctx.text_color(field)
    facts_y = last_baseline - facts.height
    name_y = facts_y - facts.style.line_height
    return [
        Text(name, x, name_y, color, "event_name", field, group="event"),
        Text(facts, x, facts_y, color, "event_facts", field, group="event"),
    ]


def cta(
    ctx: Context, field: str, x: float, y: float, max_width: float
) -> list[Rect | Text]:
    """§06 primary button: yellow plate, ink border and caps. ``y`` is the
    plate top."""
    if ctx.card.cta is None:
        return []
    spec = ctx.brand.raw["cta"]
    style = style_for(ctx.brand, ctx.fmt, "cta")
    pad_v, pad_h = (p * style.size for p in spec["padding_em"])
    block = set_line(style, ctx.card.cta, max_width - 2 * pad_h)
    if block is None:
        raise DoesNotFitError("CTA does not fit")
    border = ctx.fmt.px(spec["border_px"])
    plate = Box(x, y, block.width + 2 * pad_h, block.height + 2 * pad_v + 2 * border)
    colors = spec["on_matching_field"] if spec["fill"] == field else spec
    text = Text(
        block, x + pad_h, y + pad_v + border, colors["text"], "cta", colors["fill"]
    )
    return [
        Rect(
            plate,
            colors["fill"],
            "cta_plate",
            stroke=colors["border"],
            stroke_width=border,
        ),
        text,
    ]


def cta_height(ctx: Context) -> float:
    if ctx.card.cta is None:
        return 0.0
    spec = ctx.brand.raw["cta"]
    style = style_for(ctx.brand, ctx.fmt, "cta")
    return (
        style.cap_height
        + 2 * spec["padding_em"][0] * style.size
        + 2 * ctx.fmt.px(spec["border_px"])
    )


def brand_bar(ctx: Context, field: str) -> list[Rect]:
    spec = ctx.brand.raw["brand_bar"]
    if field not in spec["fields"]:
        return []
    h = ctx.deco("brand_bar_height")
    n = len(spec["order"])
    w = ctx.fmt.width / n
    y = ctx.fmt.height - h
    return [
        Rect(Box(i * w, y, w + (0.5 if i < n - 1 else 0), h), color, "brand_bar")
        for i, color in enumerate(spec["order"])
    ]


def headline(
    ctx: Context,
    max_width: float,
    max_height: float,
    size_shift: int,
    max_lines: int | None = None,
) -> TextBlock:
    options = set_best(
        ctx.brand,
        ctx.fmt,
        "headline",
        ctx.card.headline,
        Frame(max_width, max_height, max_lines or 0),
    )
    if len(options) <= size_shift:
        raise DoesNotFitError("headline does not fit")
    return options[size_shift]


def gap_below(ctx: Context, block: TextBlock, space: str = "md") -> float:
    """Baseline-to-cap gap under a block: its descenders plus clear space,
    so large headlines get proportionally more air."""
    return block.descent + ctx.space(space)


@dataclass
class Stack:
    """Text blocks stacked with baseline-to-cap gaps, positioned later."""

    items: list[tuple[str, TextBlock, str, float]]  # role, block, color, gap above

    @property
    def height(self) -> float:
        total = 0.0
        for i, (_, block, _, gap) in enumerate(self.items):
            total += block.height + (gap if i else 0)
        return total

    def place(self, x: float, top: float, field: str) -> list[Text]:
        out, y = [], top
        for i, (role, block, color, gap) in enumerate(self.items):
            if i:
                y += gap
            out.append(Text(block, x, y, color, role, field))
            y += block.height
        return out


def fits_vertically(top: float, bottom: float, height: float) -> None:
    if height > bottom - top + 0.5:
        raise DoesNotFitError("content taller than its region")


def descent_reserve(ctx: Context) -> float:
    """Descender depth of the largest headline step: the most a headline's
    gap to the next block can grow before the headline is sized."""
    style = style_for(
        ctx.brand, ctx.fmt, "headline", max(role_sizes(ctx.brand, "headline"))
    )
    return style.descent


def speaker_color(ctx: Context, field: str) -> str:
    """Names take the field's accent where it is legible as text (blue on
    white, yellow on ink), the text colour where it is not (yellow on blue)."""
    brand = ctx.brand
    accent = ctx.accent(field)
    if (
        contrast(brand.color(accent), brand.color(field))
        >= brand.raw["min_text_contrast"]
    ):
        return accent
    return ctx.text_color(field)


def people(ctx: Context, field: str, width: float, height: float) -> Stack | None:
    """Speaker names (never broken inside), plus the affiliation when a
    single speaker has one. None when the card names nobody, or when the
    names already are the headline."""
    card = ctx.card
    if not card.speakers or card.speaker_line == card.headline:
        return None
    items = [
        (
            "speaker",
            speaker_block(ctx, width, height * 0.4),
            speaker_color(ctx, field),
            0.0,
        )
    ]
    if len(card.speakers) == 1 and card.speakers[0].affiliation:
        affiliation = text_block(
            ctx, "meta", card.speakers[0].affiliation, width, height
        )
        items.append(
            ("affiliation", affiliation, ctx.text_color(field), ctx.space("sm"))
        )
    return Stack(items)


def body(
    ctx: Context,
    field: str,
    region: Box,
    params: dict[str, Any],
    lead: TextBlock | None = None,
) -> tuple[Stack, float]:
    """The card's message as one stack: [kicker,] headline, subline, people —
    whatever the card has. The supporting blocks are set first, so the
    headline takes exactly the room they leave. Returns the stack and the
    height the CTA adds below it."""
    color = ctx.text_color(field)
    card = ctx.card
    width, height = region.w, region.h
    sub = (
        text_block(ctx, "subline", card.subline, width, height)
        if card.subline
        else None
    )
    who = people(ctx, field, width, height)
    cta_extra = cta_height(ctx) + ctx.space("lg") if card.cta else 0.0
    reserve = sum(
        h + ctx.space("lg") + descent_reserve(ctx)
        for h in (sub and sub.height, who and who.height)
        if h
    )
    reserve += cta_extra + (lead.height + ctx.space("md") if lead else 0.0)
    hl = headline(
        ctx, width * params["measure"], height - reserve, params["size_shift"]
    )
    items = [("kicker", lead, color, 0.0)] if lead else []
    items.append(("headline", hl, color, ctx.space("md") if lead else 0.0))
    if sub:
        items.append(("subline", sub, color, gap_below(ctx, hl)))
    if who:
        first_role, first_block, first_color, _ = who.items[0]
        items.append(
            (first_role, first_block, first_color, gap_below(ctx, items[-1][1], "lg"))
        )
        items += who.items[1:]
    stack = Stack(items)
    fits_vertically(0, height, stack.height + cta_extra)
    return stack, cta_extra


def place_body(
    ctx: Context, field: str, stack: Stack, column: Box, top: float
) -> list[Rect | Text]:
    """Place a body stack at ``top`` in ``column``, the CTA below it."""
    texts = stack.place(column.x, top, field)
    if not ctx.card.cta:
        return list(texts)
    last = texts[-1]
    return [
        *texts,
        *cta(
            ctx, field, column.x, last.y + last.block.height + ctx.space("lg"), column.w
        ),
    ]


def speaker_units(ctx: Context) -> list[str]:
    names = [s.name for s in ctx.card.speakers]
    return [f"{n}," for n in names[:-1]] + names[-1:]


def speaker_block(ctx: Context, width: float, height: float) -> TextBlock:
    """Names never break internally."""
    options = set_best(
        ctx.brand, ctx.fmt, "speaker", speaker_units(ctx), Frame(width, height, 0)
    )
    if not options:
        raise DoesNotFitError("speaker names do not fit")
    return options[0]


def text_block(
    ctx: Context, role: str, text: str, max_width: float, max_height: float
) -> TextBlock:
    options = set_best(ctx.brand, ctx.fmt, role, text, Frame(max_width, max_height, 0))
    if not options:
        raise DoesNotFitError(f"{role} does not fit")
    return options[0]
