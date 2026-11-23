"""Composition strategies. Each yields brand-compliant variants of a card."""

from social_cards.layouts.base import Context, DoesNotFitError, Strategy
from social_cards.layouts.dates import Dates
from social_cards.layouts.field import Field
from social_cards.layouts.portrait import Portrait
from social_cards.layouts.python import Python
from social_cards.layouts.spine import Spine

STRATEGIES: dict[str, Strategy] = {
    s.name: s for s in (Field(), Spine(), Python(), Portrait(), Dates())
}

__all__ = ["STRATEGIES", "Context", "DoesNotFitError", "Strategy"]
