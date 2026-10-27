"""Spine: the §06 card — a coloured accent bar beside the type.

The website's session and masterclass cards: white (or the key-dates ink)
ground, a solid spine on the left, kicker, title, then the people. The
seven-colour brand bar closes the foot, as in the site footer.
"""

from collections.abc import Iterator
from typing import Any

from social_cards.composition import Box, Composition, Rect, Text
from social_cards.layouts.base import (
    Context,
    DoesNotFitError,
    Strategy,
    brand_bar,
    descent_reserve,
    event_lines,
    fits_vertically,
    gap_below,
    headline,
    kicker,
    logo,
    logo_box,
    logo_gap,
    people,
)

# Logo height as a share of the content height.
LOGO_LANDSCAPE = 0.36
LOGO_VERTICAL = 0.2


class Spine(Strategy):
    name = "spine"

    def variants(self, ctx: Context, fields: list[str]) -> Iterator[dict[str, Any]]:
        for field in fields:
            colors = [c for c in ctx.brand.raw["spine_colors"] if c != field]
            for color in ctx.pick(colors, 2, f"spine:{field}"):
                for mode in ("corner_top", "corner_bottom"):
                    # follow: people under the title; bottom: people on the
                    # foot; low: title and people together on the foot.
                    base = {
                        "field": field,
                        "spine": color,
                        "logo": mode,
                        "measure": 1.0,
                        "size_shift": 0,
                    }
                    for anchor in ("follow", "bottom", "low"):
                        yield {**base, "speakers": anchor}
                # Title and people run full width above a bottom-corner logo.
                yield {**base, "speakers": "follow", "wrap": "above"}

    def build(self, ctx: Context, params: dict[str, Any]) -> Composition:
        field = params["field"]
        content = ctx.content
        comp = Composition(ctx.fmt, field, self.name, params)
        comp.elements += brand_bar(ctx, field)

        spine_w = ctx.deco("spine_width")
        comp.elements.append(
            Rect(
                Box(content.x, content.y, spine_w, content.h), params["spine"], "spine"
            )
        )
        x0 = content.x + spine_w + ctx.space("md")

        h = content.h * (LOGO_LANDSCAPE if ctx.fmt.landscape else LOGO_VERTICAL)
        y = content.y if params["logo"] == "corner_top" else content.bottom - h
        box = logo_box(ctx, h, content.right, y, align_right=True)
        comp.elements.append(logo(ctx, field, box))
        col_w = box.x - logo_gap(ctx, box) - x0

        foot = event_lines(ctx, field, x0, col_w, content.bottom)
        region_bottom = foot[0].y - ctx.space("lg")
        if params.get("wrap") == "above":
            col_w = content.right - x0
            region_bottom = box.y - logo_gap(ctx, box)
        k = kicker(ctx, field, x0, content.y, col_w)
        region_top = content.y
        if k is not None:
            comp.elements.append(k)
            region_top = k.y + k.block.height + ctx.space("md")

        color = ctx.text_color(field)
        who = people(ctx, field, col_w, region_bottom - region_top)
        people_h = who.height if who else 0.0
        reserve = people_h + ctx.space("lg") + descent_reserve(ctx) if who else 0.0

        measure = col_w * params["measure"]
        hl = headline(
            ctx, measure, region_bottom - region_top - reserve, params["size_shift"]
        )
        hl_top = region_top
        if params["speakers"] == "low":
            group = hl.height + (gap_below(ctx, hl, "lg") + people_h if who else 0.0)
            hl_top = max(region_top, region_bottom - group)
        comp.elements.append(Text(hl, x0, hl_top, color, "headline", field))

        placed: list[Text] = []
        if who:
            follow_top = hl_top + hl.height + gap_below(ctx, hl, "lg")
            people_top = (
                region_bottom - people_h
                if params["speakers"] == "bottom"
                else follow_top
            )
            if people_top < follow_top - 0.5:
                raise DoesNotFitError("speakers collide with the headline")
            placed = who.place(x0, people_top, field)
            fits_vertically(
                region_top, region_bottom, people_top + people_h - region_top
            )
        comp.elements += placed + foot
        return comp
