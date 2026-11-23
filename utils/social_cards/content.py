"""Card content: the input model and the analysis that drives layout choice.

Content is taken verbatim — the engine may break lines and choose sizes, but
never rewords, truncates or reorders what the author wrote. Missing required
fields are errors, not defaults.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from social_cards.brand import EVENTS, REPO_ROOT, Brand
from social_cards.sponsor_logo import SponsorLogoError, load_sponsor_logo

LANGUAGES = ("en", "de")
REQUIRED = ("id", "category", "lang", "headline", "formats")
OPTIONAL = (
    "kicker",
    "subline",
    "speakers",
    "cta",
    "image",
    "image_focus_y",
    "dates",
    "event",
    "sponsor_logo",
)


class CardContentError(ValueError):
    """A card definition is incomplete or invalid."""


@dataclass(frozen=True)
class Speaker:
    name: str
    affiliation: str = ""


@dataclass(frozen=True)
class DateRow:
    date: str
    label: str


@dataclass(frozen=True)
class Card:
    id: str
    category: str
    lang: str
    headline: str
    formats: tuple[str, ...]
    kicker: str | None = None
    subline: str | None = None
    speakers: tuple[Speaker, ...] = ()
    cta: str | None = None
    image: Path | None = None
    image_focus_y: float | None = None
    dates: tuple[DateRow, ...] = ()
    # Whose dates the event facts show: "conference" or "masterclasses".
    event: str = "conference"
    # Thank-you cards: the sponsor's logo file (SVG or transparent PNG).
    sponsor_logo: Path | None = None

    def kicker_text(self, brand: Brand) -> str:
        """Explicit kicker, else the category label in the card's language."""
        if self.kicker is not None:
            return self.kicker
        label = brand.category(self.category)["label"][self.lang]
        # 'KEY DATES' over a 'Key dates' headline says the same thing twice.
        return "" if label.casefold() == self.headline.casefold() else label

    @property
    def speaker_line(self) -> str:
        return ", ".join(s.name for s in self.speakers)


@dataclass(frozen=True)
class Analysis:
    """What the content asks of a layout, deciding which strategies apply.
    Length needs no label here: the typesetter measures it exactly."""

    speakers: int
    has_image: bool
    has_dates: bool
    has_cta: bool
    has_sponsor_logo: bool


def analyse(card: Card) -> Analysis:
    return Analysis(
        speakers=len(card.speakers),
        has_image=card.image is not None,
        has_dates=bool(card.dates),
        has_cta=card.cta is not None,
        has_sponsor_logo=card.sponsor_logo is not None,
    )


def _speakers(card_id: str, raw: list) -> tuple[Speaker, ...]:
    speakers = []
    for s in raw:
        if isinstance(s, str):
            speakers.append(Speaker(name=s))
        elif "name" in s:
            speakers.append(
                Speaker(name=s["name"], affiliation=s.get("affiliation", ""))
            )
        else:
            raise CardContentError(f"card {card_id}: every speaker needs a name")
    return tuple(speakers)


def _dates(card_id: str, raw: list) -> tuple[DateRow, ...]:
    rows = []
    for row in raw:
        if not row.get("date") or not row.get("label"):
            raise CardContentError(
                f"card {card_id}: every date row needs 'date' and 'label'"
            )
        rows.append(DateRow(date=str(row["date"]), label=row["label"]))
    return tuple(rows)


def _image(card_id: str, data: dict[str, Any]) -> tuple[Path | None, float | None]:
    if not data.get("image"):
        return None, None
    image = (REPO_ROOT / data["image"]).resolve()
    if not image.is_file():
        raise CardContentError(f"card {card_id}: image not found: {image}")
    focus = data.get("image_focus_y")
    if focus is not None and not 0 <= focus <= 1:
        raise CardContentError(f"card {card_id}: image_focus_y must be between 0 and 1")
    return image, focus


def sponsor_logo_path(card_id: str, category: str, path: Path, brand: Brand) -> Path:
    """The logo file, once it is known to show faithfully on the card's
    background; a CardContentError says why it cannot."""
    try:
        load_sponsor_logo(path, brand, brand.field_for(card_id, category))
    except SponsorLogoError as err:
        raise CardContentError(f"card {card_id}: {err}") from None
    return path


def _sponsor_logo(card_id: str, data: dict[str, Any], brand: Brand) -> Path | None:
    if not data.get("sponsor_logo"):
        return None
    path = (REPO_ROOT / data["sponsor_logo"]).resolve()
    return sponsor_logo_path(card_id, data["category"], path, brand)


def _check_fields(card_id: str, data: dict[str, Any], brand: Brand) -> None:
    missing = [k for k in REQUIRED if not data.get(k)]
    if missing:
        raise CardContentError(
            f"card {card_id}: missing required field(s) {', '.join(missing)}"
        )
    unknown = set(data) - set(REQUIRED) - set(OPTIONAL)
    if unknown:
        raise CardContentError(
            f"card {card_id}: unknown field(s) {', '.join(sorted(unknown))}"
        )
    brand.category(data["category"])  # raises for unknown categories
    if data["lang"] not in LANGUAGES:
        raise CardContentError(f"card {card_id}: lang must be one of {LANGUAGES}")
    if data.get("event", "conference") not in EVENTS:
        raise CardContentError(f"card {card_id}: event must be one of {EVENTS}")
    for fmt in data["formats"]:
        brand.format(fmt)  # raises for unknown formats


def card_from_dict(data: dict[str, Any], brand: Brand) -> Card:
    card_id = str(data.get("id", "<no id>"))
    _check_fields(card_id, data, brand)
    image, focus = _image(card_id, data)
    return Card(
        id=card_id,
        category=data["category"],
        lang=data["lang"],
        headline=data["headline"],
        formats=tuple(data["formats"]),
        kicker=data.get("kicker"),
        subline=data.get("subline"),
        speakers=_speakers(card_id, data.get("speakers", [])),
        cta=data.get("cta"),
        image=image,
        image_focus_y=focus,
        dates=_dates(card_id, data.get("dates", [])),
        event=data.get("event", "conference"),
        sponsor_logo=_sponsor_logo(card_id, data, brand),
    )


def load_cards(path: Path, brand: Brand) -> list[Card]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "cards" not in data:
        raise CardContentError(f"{path}: expected a top-level 'cards' list")
    cards = [card_from_dict(c, brand) for c in data["cards"]]
    ids = [c.id for c in cards]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise CardContentError(
            f"{path}: duplicate card id(s) {', '.join(sorted(duplicates))}"
        )
    return cards
