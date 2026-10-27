"""Generate the social card of every talk in databags/talks.json.

Each card is designed by the social_cards engine (brand-validated, scored,
refined) and written to static/media/social/talks/{code}.png, the path
utils/talks.py puts into every talk page's `social_card_image`.

A JSON file next to each card records what it was made from. A card is only
redrawn when its title, speakers, session type or the brand spec changed,
so a submissions fetch does not churn hundreds of unchanged images.
"""

import hashlib
import json
from pathlib import Path

from social_cards.brand import SPEC_PATH, load_brand
from social_cards.composition import Composition
from social_cards.content import Card, Speaker
from social_cards.pipeline import design, export

src_path = Path(__file__).parents[1]
TALKS_JSON = src_path / "databags/talks.json"
CARDS_DIR = src_path / "assets/static/media/social/talks"
FORMAT = "og"


def load_talks() -> list[dict]:
    with TALKS_JSON.open() as f:
        return json.load(f)["talks"]


def spec_fingerprint() -> str:
    """Changes whenever the brand spec does, so every card is redrawn."""
    return hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()[:16]


def talk_card(talk: dict) -> Card:
    """Talks are listed in English on the site; the session type from
    Pretalx is the kicker, as on the website's session cards."""
    category = "keynote" if talk.get("is_keynote") else "talk"
    names = [n.strip() for n in talk["speaker_names"].split(", ") if n.strip()]
    return Card(
        id=talk["code"],
        category=category,
        lang="en",
        headline=talk["title"],
        formats=(FORMAT,),
        kicker=talk.get("submission_type_label") or None,
        speakers=tuple(Speaker(name=n) for n in names),
    )


def card_record(talk: dict, fingerprint: str) -> dict:
    return {
        "title": talk["title"],
        "speaker_names": talk["speaker_names"],
        "submission_type_label": talk.get("submission_type_label", ""),
        "spec": fingerprint,
    }


def generate(talks: list[dict], out_dir: Path) -> list[str]:
    """Draw the cards that are missing or out of date; returns their codes."""
    brand = load_brand()
    fingerprint = spec_fingerprint()
    history: list[Composition] = []
    drawn = []
    for talk in talks:
        png = out_dir / f"{talk['code']}.png"
        record_path = out_dir / f"{talk['code']}.json"
        record = card_record(talk, fingerprint)
        if (
            png.exists()
            and record_path.exists()
            and json.loads(record_path.read_text()) == record
        ):
            continue
        result = design(talk_card(talk), FORMAT, brand, history)
        export(result, brand, png)
        history.append(result.chosen.comp)
        record_path.write_text(json.dumps(record))
        drawn.append(talk["code"])
        print(result.report())
    return drawn


def main() -> None:
    drawn = generate(load_talks(), CARDS_DIR)
    print(f"{len(drawn)} talk card(s) drawn")


if __name__ == "__main__":
    main()
