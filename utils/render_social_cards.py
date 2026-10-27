"""Render PyCon DE 2027 social cards from a YAML card file.

    uv run --extra cards python utils/render_social_cards.py CARDS.yaml --out DIR
        [--formats og,square] [--only ID,ID] [--sheet SHEET.png] [--verbose]

Every card is designed for each of its formats (or the --formats subset):
candidates are generated, validated against the brand spec, scored and
refined, and the winner is written to DIR/{id}-{format}.png. A card for
which no candidate passes validation is an error; nothing is written for it.
"""

import argparse
import sys
from pathlib import Path

from social_cards.brand import load_brand
from social_cards.composition import Composition
from social_cards.content import load_cards
from social_cards.pipeline import NoValidDesignError, design, export
from social_cards.sheet import contact_sheet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "cards", type=Path, help="YAML file with a top-level 'cards' list"
    )
    parser.add_argument("--out", type=Path, required=True, help="output directory")
    parser.add_argument("--formats", help="comma-separated subset of formats to render")
    parser.add_argument("--only", help="comma-separated card ids to render")
    parser.add_argument(
        "--sheet", type=Path, help="also write a contact sheet with the reference card"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="print the top candidates and rejections"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    brand = load_brand()
    cards = load_cards(args.cards, brand)
    if args.only:
        wanted = set(args.only.split(","))
        unknown = wanted - {c.id for c in cards}
        if unknown:
            sys.exit(f"unknown card id(s): {', '.join(sorted(unknown))}")
        cards = [c for c in cards if c.id in wanted]
    formats = args.formats.split(",") if args.formats else None

    history: dict[str, list[Composition]] = {}
    rendered = []
    failures = 0
    for card in cards:
        for fmt in card.formats:
            if formats and fmt not in formats:
                continue
            try:
                result = design(card, fmt, brand, history.setdefault(fmt, []))
            except NoValidDesignError as err:
                print(f"FAILED {err}", file=sys.stderr)
                failures += 1
                continue
            export(result, brand, args.out / f"{card.id}-{fmt}.png")
            history[fmt].append(result.chosen.comp)
            rendered.append(
                (
                    f"{card.id} · {fmt} · {result.chosen.comp.strategy} · {result.chosen.score.total:.1f}",
                    result.image,
                )
            )
            print(result.report())
            if args.verbose:
                for cand in result.ranking[1:4]:
                    print(f"      runner-up {cand.comp.key}  {cand.score}")
                for key, reason in result.rejected[:6]:
                    print(f"      rejected {key}: {reason}")
    if args.sheet and rendered:
        print(f"contact sheet: {contact_sheet(rendered, args.sheet)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
