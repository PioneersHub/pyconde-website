"""Thanks: the sponsor thank-you card, with the sponsor's logo as its hero.

The website's sponsor wall shows each logo in its own colours on a warm
off-white; this card does the same. The tier is the kicker and the
thank-you the headline, across the full width. The PyCon DE monogram signs
the card at the bottom right, beside the event facts.

Every sponsor's logo gets the same area in a format (`sponsor_logo.area` in
brand.yaml), so a square mark and a long wordmark carry the same weight. A
layout that would shrink a logo below that area is not used, unless the
logo already spans the full width; that is how compact logos end up in the
split layout on landscape cards and wide wordmarks under the headline.

Two layouts:

- stage: thank-you on top, the logo centred in the space below it;
- split (landscape only): thank-you and facts on the left, the logo
  centred on the right.
"""

from collections.abc import Iterator
from math import sqrt
from typing import Any

from social_cards.composition import Box, Composition, Raster, Text
from social_cards.layouts.base import (
    Context,
    DoesNotFitError,
    Stack,
    Strategy,
    brand_bar,
    event_lines,
    kicker,
    logo,
    logo_box,
    logo_gap,
)
from social_cards.sponsor_logo import load_sponsor_logo
from social_cards.typeset import Frame, TextBlock, set_best

# Most of the content height the thank-you may take.
HEADLINE_SHARE = 0.34
# Share of the content width the text column takes in the split layout.
SPLIT_TEXT_SHARE = 0.5
# Landscape cards may set the thank-you on one line or two; vertical cards
# always take the large two-line setting ("Thank you / for your support!").
LANDSCAPE_LINES = (1, 2)
VERTICAL_LINES = (2,)


class Thanks(Strategy):
    name = "thanks"

    def applicable(self, ctx: Context) -> bool:
        return ctx.analysis.has_sponsor_logo

    def variants(self, ctx: Context, fields: list[str]) -> Iterator[dict[str, Any]]:
        landscape = ctx.fmt.landscape
        layouts = ("stage", "split") if landscape else ("stage",)
        line_counts = LANDSCAPE_LINES if landscape else VERTICAL_LINES
        for field in fields:
            for layout in layouts:
                for lines in line_counts:
                    for bar in (True, False):
                        yield {
                            "field": field,
                            "layout": layout,
                            "lines": lines,
                            "bar": bar,
                            "measure": 1.0,
                            "size_shift": 0,
                        }

    def build(self, ctx: Context, params: dict[str, Any]) -> Composition:
        field = params["field"]
        content = ctx.content
        comp = Composition(ctx.fmt, field, self.name, params)
        if params["bar"]:
            comp.elements += brand_bar(ctx, field)
            if not comp.elements:
                raise DoesNotFitError(f"no brand bar on {field}")

        # Signature: the monogram at its minimum, bottom right.
        mono_h = ctx.fmt.px(ctx.brand.raw["logo"]["min_height"])
        mono = logo_box(ctx, mono_h, content.right, content.bottom - mono_h, True)
        comp.elements.append(logo(ctx, field, mono))
        gap = logo_gap(ctx, mono)

        split = params["layout"] == "split"
        text_w = content.w * SPLIT_TEXT_SHARE if split else content.w
        facts_w = (text_w if split else mono.x - gap) - content.x
        foot = event_lines(ctx, field, content.x, facts_w, content.bottom)
        texts = self._thank_you(ctx, field, params, text_w)
        comp.elements += texts + foot

        lg = ctx.space("lg")
        if split:
            x = content.x + text_w + gap
            stage = Box(x, content.y, content.right - x, mono.y - lg - content.y)
        else:
            top = texts[-1].layout_box.bottom + lg
            bottom = min(foot[0].y, mono.y) - lg
            stage = Box(content.x, top, content.w, bottom - top)
        comp.elements.append(self._sponsor_logo(ctx, field, stage))
        return comp

    def _thank_you(
        self, ctx: Context, field: str, params: dict[str, Any], width: float
    ) -> list[Text]:
        """Kicker and headline at the top of the text column. The headline
        takes the size step `size_shift` among settings on `lines` lines."""
        content = ctx.content
        k = kicker(ctx, field, content.x, content.y, width)
        lead = k.block.height + ctx.space("md") if k else 0.0
        frame = Frame(width * params["measure"], content.h * HEADLINE_SHARE - lead, 0)
        options: list[TextBlock] = [
            b
            for b in set_best(ctx.brand, ctx.fmt, "headline", ctx.card.headline, frame)
            if len(b.lines) == params["lines"]
        ]
        if len(options) <= params["size_shift"]:
            raise DoesNotFitError(f"headline does not fit on {params['lines']} lines")
        hl = options[params["size_shift"]]
        color = ctx.text_color(field)
        items = [("kicker", k.block, color, 0.0)] if k else []
        items.append(("headline", hl, color, ctx.space("md") if k else 0.0))
        return Stack(items).place(content.x, content.y, field)

    def _sponsor_logo(self, ctx: Context, field: str, stage: Box) -> Raster:
        """The logo at the format's common area, centred in its stage."""
        sponsor = load_sponsor_logo(ctx.card.sponsor_logo, ctx.brand, field)
        spec = ctx.brand.raw["sponsor_logo"]
        area = spec["area"][ctx.fmt.name] * ctx.content.w * ctx.content.h
        w, h = sqrt(area * sponsor.aspect), sqrt(area / sponsor.aspect)
        # The logo's clear space is reserved inside the stage with it.
        clear = 2 * spec["clear_space_ratio"] * min(w, h)
        width_fit, height_fit = stage.w / (w + clear), stage.h / (h + clear)
        fit = min(1.0, width_fit, height_fit)
        spans_width = width_fit <= height_fit and stage.w >= ctx.content.w - 0.5
        if fit * fit < spec["min_fit"] and not spans_width:
            raise DoesNotFitError(
                f"sponsor logo would shrink to {fit * fit:.0%} of the common logo area"
            )
        w, h = w * fit, h * fit
        # A long wordmark at the common area can be too thin to read: it is
        # raised to the minimum height when the stage is wide enough.
        min_h = ctx.fmt.px(spec["min_height"])
        if h < min_h:
            grow = min_h / h
            if (w + clear * fit) * grow > stage.w + 0.5:
                raise DoesNotFitError(
                    f"sponsor logo would be {h:.0f}px tall, below its minimum"
                )
            w, h = w * grow, min_h
        box = Box(stage.x + (stage.w - w) / 2, stage.y + (stage.h - h) / 2, w, h)
        return Raster(sponsor.path, box, "sponsor_logo")
