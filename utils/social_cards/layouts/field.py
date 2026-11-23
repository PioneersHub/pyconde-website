"""Field: a full brand-colour field, the monogram and a display headline.

The website's section voice (intro, tickets, sponsoring, newsletter,
masterclasses): one flat colour, left-aligned type, the logo as the anchor.
Logo placement varies — a full-height monogram column, or a smaller mark in
a corner — and the message either hangs from the kicker or sits on the
event facts at the foot.
"""

from collections.abc import Iterator
from typing import Any

from social_cards.composition import Box, Composition
from social_cards.layouts.base import (
    Context,
    Strategy,
    body,
    event_lines,
    kicker,
    logo,
    logo_box,
    logo_gap,
    place_body,
)

# Logo height as a share of the content height, per placement.
TOP_LOGO = 0.34
CORNER_LOGO_LANDSCAPE = 0.42
CORNER_LOGO_VERTICAL = 0.26


class Field(Strategy):
    name = "field"

    def variants(self, ctx: Context, fields: list[str]) -> Iterator[dict[str, Any]]:
        modes = (
            ("column", "corner_top", "corner_bottom")
            if ctx.fmt.landscape
            else ("top", "corner_bottom")
        )
        for field in fields:
            for mode in modes:
                base = {"field": field, "logo": mode, "measure": 1.0, "size_shift": 0}
                for anchor in ("top", "bottom"):
                    yield {**base, "anchor": anchor}
                if mode == "corner_bottom":
                    # The message runs full width above the logo instead of
                    # in a narrow column beside it.
                    yield {**base, "anchor": "top", "wrap": "above"}

    def neighbours(
        self, ctx: Context, params: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        yield from super().neighbours(ctx, params)
        if params["logo"] != "column":
            for scale in (0.8, 1.2):
                yield {
                    **params,
                    "logo_scale": round(params.get("logo_scale", 1.0) * scale, 3),
                }

    def _logo_and_column(self, ctx: Context, params: dict[str, Any]) -> tuple[Box, Box]:
        """Where the monogram goes, and the text column it leaves free."""
        content, mode = ctx.content, params["logo"]
        scale = params.get("logo_scale", 1.0)
        if mode == "column":
            box = logo_box(ctx, content.h, content.x, content.y)
            x0 = box.right + logo_gap(ctx, box)
            return box, Box(x0, content.y, content.right - x0, content.h)
        if mode == "top":
            box = logo_box(ctx, content.h * TOP_LOGO * scale, content.x, content.y)
            top = box.bottom + logo_gap(ctx, box)
            return box, Box(content.x, top, content.w, content.bottom - top)
        share = CORNER_LOGO_LANDSCAPE if ctx.fmt.landscape else CORNER_LOGO_VERTICAL
        h = content.h * share * scale
        y = content.y if mode == "corner_top" else content.bottom - h
        box = logo_box(ctx, h, content.right, y, align_right=True)
        return box, Box(
            content.x, content.y, box.x - logo_gap(ctx, box) - content.x, content.h
        )

    def build(self, ctx: Context, params: dict[str, Any]) -> Composition:
        field = params["field"]
        content = ctx.content
        comp = Composition(ctx.fmt, field, self.name, params)
        box, col = self._logo_and_column(ctx, params)
        comp.elements.append(logo(ctx, field, box))

        # Event facts sit on the bottom line; under a top logo they may use
        # the full width.
        full_foot = params["logo"] in ("top", "corner_top")
        foot_x, foot_w = (content.x, content.w) if full_foot else (col.x, col.w)
        foot = event_lines(ctx, field, foot_x, foot_w, content.bottom)
        region = Box(col.x, col.y, col.w, foot[0].y - ctx.space("lg") - col.y)
        if params.get("wrap") == "above":
            region = Box(
                content.x, content.y, content.w, box.y - logo_gap(ctx, box) - content.y
            )

        # The kicker leads the stack, so it stays with the headline wherever
        # the message is anchored.
        k = kicker(ctx, field, region.x, 0, region.w)
        stack, cta_extra = body(ctx, field, region, params, lead=k.block if k else None)
        top = (
            region.y
            if params["anchor"] == "top"
            else region.bottom - stack.height - cta_extra
        )
        comp.elements += place_body(ctx, field, stack, region, top) + foot
        return comp
