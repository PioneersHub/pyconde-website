"""Python: an official python illustration as the counterweight to the type.

§05 / blog fallback: the python artwork lives on the blue field. Type sits
on the opposite side, bottom-anchored on the event facts, so the python and
the headline balance diagonally. On any other field only pythons without a
body segment in the field colour are used.
"""

from collections.abc import Iterator
from typing import Any

from social_cards.art import eligible
from social_cards.composition import Box, Composition, Raster
from social_cards.layouts.base import (
    Context,
    DoesNotFitError,
    Strategy,
    body,
    event_lines,
    kicker,
    logo,
    logo_box,
)

# Share of the content width the artwork may take (refinement steps).
ART_SHARES = (0.38, 0.42, 0.46, 0.5)
# On vertical cards the artwork spans more of the width, less of the height.
VERTICAL_WIDTH_FACTOR = 1.6
VERTICAL_HEIGHT_FACTOR = 0.95
# The logo is a signature here, just above its minimum size.
LOGO_OVER_MINIMUM = 1.15


class Python(Strategy):
    name = "python"

    def applicable(self, ctx: Context) -> bool:
        # Artwork and people or a call to action compete; this stays quiet.
        return not ctx.analysis.speakers and not ctx.analysis.has_cta

    def variants(self, ctx: Context, fields: list[str]) -> Iterator[dict[str, Any]]:
        for field in fields:
            arts = eligible(ctx.brand, field)
            for art in ctx.pick(arts, 3, f"python:{field}"):
                for align in ("bottom", "center"):
                    yield {
                        "field": field,
                        "python": art.path.stem,
                        "align": align,
                        "art_share": 0.46,
                        "measure": 1.0,
                        "size_shift": 0,
                    }

    def neighbours(
        self, ctx: Context, params: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        yield from super().neighbours(ctx, params)
        for share in ART_SHARES:
            if share != params["art_share"]:
                yield {**params, "art_share": share}

    def build(self, ctx: Context, params: dict[str, Any]) -> Composition:
        field = params["field"]
        art = next(
            (a for a in eligible(ctx.brand, field) if a.path.stem == params["python"]),
            None,
        )
        if art is None:
            raise DoesNotFitError(f"{params['python']} is not allowed on {field}")
        content = ctx.content
        comp = Composition(ctx.fmt, field, self.name, params)
        share = params["art_share"]
        gap = ctx.space("lg")

        if ctx.fmt.landscape:
            region = Box(
                content.right - content.w * share,
                content.y,
                content.w * share,
                content.h,
            )
        else:
            w = content.w * share * VERTICAL_WIDTH_FACTOR
            region = Box(
                content.right - w,
                content.y,
                w,
                content.h * share * VERTICAL_HEIGHT_FACTOR,
            )
        w = min(region.w, region.h * art.aspect)
        h = w / art.aspect
        x = region.right - w
        if ctx.fmt.landscape:
            y = (
                region.bottom - h
                if params["align"] == "bottom"
                else region.y + (region.h - h) / 2
            )
        else:
            y = (
                region.y
                if params["align"] == "bottom"
                else region.y + (region.h - h) / 2
            )
        art_box = Box(x, y, w, h)
        comp.elements.append(Raster(art.path, art_box, "python", colors=art.colors))

        logo_h = ctx.fmt.px(ctx.brand.raw["logo"]["min_height"]) * LOGO_OVER_MINIMUM
        lbox = logo_box(ctx, logo_h, content.x, content.y)
        comp.elements.append(logo(ctx, field, lbox))

        if ctx.fmt.landscape:
            col = Box(content.x, content.y, art_box.x - gap - content.x, content.h)
            text_top = lbox.bottom + gap
        else:
            col = Box(content.x, content.y, content.w, content.h)
            text_top = max(lbox.bottom, art_box.bottom) + gap

        foot = event_lines(ctx, field, col.x, col.w, content.bottom)
        region_bottom = foot[0].y - ctx.space("lg")
        # The kicker leads the bottom-anchored stack: top-left is the logo's.
        k = kicker(ctx, field, col.x, 0, col.w)
        region = Box(col.x, text_top, col.w, region_bottom - text_top)
        stack, _ = body(ctx, field, region, params, lead=k.block if k else None)
        comp.elements += stack.place(col.x, region_bottom - stack.height, field) + foot
        return comp
