"""Dates: the front-page key-dates list as a card.

Ink ground (#1a1a1a, .keydates), each row a bold date over its label with a
coloured spine on the left, exactly like `.keydates__item`. Title and logo
take the left column on landscape cards and the top on vertical ones.
"""

from collections.abc import Iterator
from typing import Any

from social_cards.composition import Box, Composition, Rect, Text
from social_cards.layouts.base import (
    Context,
    DoesNotFitError,
    Strategy,
    clear_space,
    event_lines,
    fits_vertically,
    headline,
    kicker,
    logo,
    logo_box,
)
from social_cards.typeset import Frame, TextBlock, role_sizes, set_block, style_for


class Dates(Strategy):
    name = "dates"

    def applicable(self, ctx: Context) -> bool:
        return ctx.analysis.has_dates

    def variants(self, ctx: Context, fields: list[str]) -> Iterator[dict[str, Any]]:
        splits = (0.4, 0.46) if ctx.fmt.landscape else (0.0,)
        for field in fields:
            for split in splits:
                yield {"field": field, "split": split, "measure": 1.0, "size_shift": 0}

    def neighbours(
        self, _ctx: Context, params: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        for shift in (params["size_shift"] - 1, params["size_shift"] + 1):
            if shift >= 0:
                yield {**params, "size_shift": shift}

    def _rows(
        self, ctx: Context, width: float, height: float
    ) -> list[tuple[TextBlock, TextBlock]]:
        """Largest row size at which every date and label fits."""
        brand, fmt = ctx.brand, ctx.fmt
        gap = ctx.space("md")
        for date_size, label_size in zip(
            role_sizes(brand, "date"), role_sizes(brand, "date_label"), strict=True
        ):
            ds = style_for(brand, fmt, "date", date_size)
            ls = style_for(brand, fmt, "date_label", label_size)
            rows = []
            for row in ctx.card.dates:
                d = set_block(brand, row.date, ds, Frame(width, lines=1))
                lab = set_block(brand, row.label, ls, Frame(width, lines=2))
                if d is None or lab is None:
                    break
                rows.append((d, lab))
            else:
                total = sum(self._row_height(ctx, d, lab) for d, lab in rows) + gap * (
                    len(rows) - 1
                )
                if total <= height:
                    return rows
        raise DoesNotFitError("date rows do not fit")

    def _row_height(self, ctx: Context, d: TextBlock, lab: TextBlock) -> float:
        return d.height + ctx.space("sm") + lab.height + lab.descent

    def build(self, ctx: Context, params: dict[str, Any]) -> Composition:
        field = params["field"]
        fmt, content = ctx.fmt, ctx.content
        comp = Composition(fmt, field, self.name, params)
        color = ctx.text_color(field)
        spine_w = ctx.deco("spine_width")
        gap = ctx.space("lg")

        if fmt.landscape:
            left = Box(content.x, content.y, content.w * params["split"], content.h)
            right = Box(
                left.right + gap, content.y, content.right - left.right - gap, content.h
            )
            lbox = logo_box(
                ctx, content.h * 0.42, left.x, left.bottom - content.h * 0.42
            )
            title_area = Box(
                left.x, left.y, left.w, lbox.y - clear_space(ctx, lbox) - left.y
            )
            inner = right.x + spine_w + ctx.space("md")
            foot = event_lines(ctx, field, inner, right.right - inner, content.bottom)
            rows_area = Box(right.x, right.y, right.w, foot[0].y - gap - right.y)
        else:
            lbox = logo_box(
                ctx, content.h * 0.16, content.right, content.y, align_right=True
            )
            title_area = Box(
                content.x,
                content.y,
                lbox.x - clear_space(ctx, lbox) - content.x,
                content.h * 0.4,
            )
            foot = event_lines(ctx, field, content.x, content.w, content.bottom)
            rows_area = None
        comp.elements.append(logo(ctx, field, lbox))

        k = kicker(ctx, field, title_area.x, title_area.y, title_area.w)
        top = title_area.y
        if k:
            comp.elements.append(k)
            top = k.y + k.block.height + ctx.space("md")
        # The title's descenders must stay clear of the logo zone below it.
        room = title_area.bottom - top - ctx.fmt.px(36)
        hl = headline(
            ctx,
            title_area.w * params["measure"],
            room,
            params["size_shift"],
            max_lines=3,
        )
        comp.elements.append(Text(hl, title_area.x, top, color, "headline", field))

        if rows_area is None:
            rows_top = max(top + hl.height + hl.descent + gap, lbox.bottom + gap)
            rows_area = Box(content.x, rows_top, content.w, foot[0].y - gap - rows_top)

        inner_x = rows_area.x + spine_w + ctx.space("md")
        rows = self._rows(ctx, rows_area.right - inner_x, rows_area.h)
        spines = [c for c in ctx.brand.raw["spine_colors"] if c != field]
        spines = ctx.pick(spines, len(spines), "dates")
        # Rows spread into the column on tall cards, up to an 'xl' gap.
        heights = [self._row_height(ctx, d, lab) for d, lab in rows]
        spare = rows_area.h - sum(heights)
        row_gap = ctx.space("md")
        if len(rows) > 1:
            row_gap = min(max(row_gap, spare / (len(rows) - 1)), ctx.space("xl"))
        y = rows_area.y
        for i, (d, lab) in enumerate(rows):
            row_h = self._row_height(ctx, d, lab)
            comp.elements.append(
                Rect(
                    Box(rows_area.x, y, spine_w, row_h),
                    spines[i % len(spines)],
                    "spine",
                )
            )
            comp.elements.append(Text(d, inner_x, y, color, "date", field))
            comp.elements.append(
                Text(
                    lab,
                    inner_x,
                    y + d.height + ctx.space("sm"),
                    color,
                    "date_label",
                    field,
                )
            )
            y += row_h + row_gap
        fits_vertically(rows_area.y, rows_area.bottom, y - row_gap - rows_area.y)
        comp.elements += foot
        return comp
