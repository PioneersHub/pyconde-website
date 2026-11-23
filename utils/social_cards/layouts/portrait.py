"""Portrait: a speaker photo panel beside a brand-colour field.

The photo is used unaltered in a square-cornered, full-bleed panel (the
2027 rules define no photo treatment yet — see brand.yaml `photo`). Text
never sits on the photo; the field carries all type and the logo.
"""

from collections.abc import Iterator
from typing import Any

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
    logo_gap,
    place_body,
)

# Photo panel as a share of the width (landscape) or height (vertical).
PANEL_LANDSCAPE = (0.38, 0.45)
PANEL_VERTICAL = (0.5, 0.56)
# Logo height as a share of the text area.
LOGO_LANDSCAPE = 0.3
LOGO_VERTICAL = 0.34


class Portrait(Strategy):
    name = "portrait"

    def applicable(self, ctx: Context) -> bool:
        return ctx.analysis.has_image

    def variants(self, ctx: Context, fields: list[str]) -> Iterator[dict[str, Any]]:
        ratios = PANEL_LANDSCAPE if ctx.fmt.landscape else PANEL_VERTICAL
        for field in fields:
            for ratio in ratios:
                base = {"field": field, "panel": ratio, "measure": 1.0, "size_shift": 0}
                for mode in ("corner_top", "corner_bottom"):
                    yield {**base, "logo": mode}
                yield {**base, "logo": "corner_bottom", "wrap": "above"}

    def build(self, ctx: Context, params: dict[str, Any]) -> Composition:
        field = params["field"]
        fmt, content = ctx.fmt, ctx.content
        comp = Composition(fmt, field, self.name, params)
        focus = ctx.card.image_focus_y
        if focus is None:
            focus = ctx.brand.raw["photo"]["default_focus_y"]

        if fmt.landscape:
            panel = Box(0, 0, fmt.width * params["panel"], fmt.height)
            area = Box(
                panel.right + fmt.margin,
                content.y,
                content.right - panel.right - fmt.margin,
                content.h,
            )
        else:
            panel = Box(0, 0, fmt.width, fmt.height * params["panel"])
            top = max(panel.bottom + fmt.margin, content.y)
            area = Box(content.x, top, content.w, content.bottom - top)
        if area.w <= 0 or area.h <= 0:
            raise DoesNotFitError("no room beside the photo")
        comp.elements.append(Raster(ctx.card.image, panel, "photo", focus_y=focus))

        h = area.h * (LOGO_LANDSCAPE if fmt.landscape else LOGO_VERTICAL)
        y = area.y if params["logo"] == "corner_top" else area.bottom - h
        lbox = logo_box(ctx, h, area.right, y, align_right=True)
        comp.elements.append(logo(ctx, field, lbox))
        col_w = lbox.x - logo_gap(ctx, lbox) - area.x

        # Under a top logo the facts may run to the edge of the text area.
        foot_w = area.w if params["logo"] == "corner_top" else col_w
        foot = event_lines(ctx, field, area.x, foot_w, area.bottom)
        region = Box(area.x, area.y, col_w, foot[0].y - ctx.space("lg") - area.y)
        if params.get("wrap") == "above":
            region = Box(area.x, area.y, area.w, lbox.y - logo_gap(ctx, lbox) - area.y)
        k = kicker(ctx, field, region.x, 0, region.w)
        stack, _ = body(ctx, field, region, params, lead=k.block if k else None)
        comp.elements += place_body(ctx, field, stack, region, region.y) + foot
        return comp
