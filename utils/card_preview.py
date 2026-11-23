"""Local preview gallery of every social-card variant, for review and tuning.

    make card-preview
    uv run --extra cards python utils/card_preview.py [--only ID,ID]

Every sample card (the validation set in tests/social_cards/cards.yaml and
every page card that `make page-cards` would draw) is designed on each
background in brand.yaml and in each export format. The gallery shows the
card the engine picks, every other candidate it scored (with the critique
breakdown) and every variant the brand checks rejected (with the reason).

A card only ever appears on its own background, which is marked in the
gallery; the others are shown so each colour can be judged and tuned.
Edit brand.yaml, run again and reload. Nothing outside build/card-preview/
is written.
"""

import argparse
import html
import json
import re
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path

import page_social_cards as pc
from social_cards.brand import REPO_ROOT, Brand, load_brand
from social_cards.content import Card, load_cards
from social_cards.pipeline import NoValidDesignError, design
from social_cards.render import render

OUT_DIR = REPO_ROOT / "build" / "card-preview"
SAMPLE_CARDS = REPO_ROOT / "tests" / "social_cards" / "cards.yaml"
CHOSEN_WIDTH = 480  # px of the chosen card in the gallery
VARIANT_WIDTH = 240  # px of every other candidate
JPEG_QUALITY = 82


@dataclass
class Variant:
    key: str
    image: str  # path relative to OUT_DIR
    total: float
    parts: dict[str, float]
    notes: list[str]


@dataclass
class Cell:
    """One card on one background in one format."""

    card_id: str
    background: str
    fmt: str
    variants: list[Variant]  # ranked, the chosen card first
    rejected: list[tuple[str, str]]
    error: str = ""


def on_background(brand: Brand, category: str, background: str) -> Brand:
    """The brand with a single-colour pool for `category`: its cards land on
    `background`, whatever their id."""
    categories = {
        **brand.raw["categories"],
        category: {**brand.category(category), "backgrounds": [background]},
    }
    return replace(brand, raw={**brand.raw, "categories": categories})


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")


def _save(image, rel: str, width: int) -> str:
    path = OUT_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    height = round(width * image.height / image.width)
    image.convert("RGB").resize((width, height)).save(path, quality=JPEG_QUALITY)
    return rel


def preview_cell(card: Card, background: str, fmt: str) -> Cell:
    """Design one cell and save its thumbnails. Runs in a worker process."""
    brand = on_background(load_brand(), card.category, background)
    base = f"img/{_slug(card.id)}/{background}-{fmt}"
    try:
        result = design(card, fmt, brand)
    except NoValidDesignError as err:
        return Cell(card.id, background, fmt, [], [], error=str(err))
    variants = []
    for rank, cand in enumerate(result.ranking):
        width = CHOSEN_WIDTH if rank == 0 else VARIANT_WIDTH
        # The chosen card is drawn at twice its gallery size, for sharpness.
        scale = (2 if rank == 0 else 1) * width / cand.comp.fmt.width
        image = render(cand.comp, brand, scale=scale)
        variants.append(
            Variant(
                key=cand.comp.key,
                image=_save(image, f"{base}-{rank:02d}.jpg", width),
                total=cand.score.total,
                parts=dict(cand.score.parts),
                notes=sorted(set(cand.score.notes)),
            )
        )
    return Cell(card.id, background, fmt, variants, sorted(set(result.rejected)))


def sample_cards(brand: Brand) -> tuple[list[Card], list[str]]:
    """The validation set plus every page card (preview-only recipes
    included), and why any page cannot get a card at all."""
    cards = load_cards(SAMPLE_CARDS, brand)
    config = pc.load_config()
    problems = []
    for page_dir, model in pc.pages(pc.CONTENT_DIR, config, preview=True):
        try:
            cards.append(pc.card_for(page_dir, model, pc.CONTENT_DIR, config, brand))
        except pc.PageCardError as err:
            problems.append(str(err))
    return cards, problems


# ── HTML ─────────────────────────────────────────────────────

STYLE = """
:root { --ink: #1a1a1a; --muted: #5d6670; --line: #dde1e4; --mark: #3778be; }
* { box-sizing: border-box; }
body { margin: 0; font: 14px/1.45 system-ui, sans-serif; color: var(--ink); background: #f4f5f6; }
header, main { max-width: 1600px; margin: 0 auto; padding: 16px; }
h1 { font-size: 22px; margin: 0 0 4px; } h2 { font-size: 18px; margin: 32px 0 8px; }
h3 { font-size: 15px; margin: 20px 0 8px; } p { margin: 4px 0; color: var(--muted); }
a { color: var(--mark); }
.index { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.index a { display: block; background: #fff; border: 1px solid var(--line); padding: 8px; text-decoration: none; color: inherit; }
.index img { width: 100%; display: block; margin-bottom: 6px; }
.matrix { display: grid; gap: 12px; overflow-x: auto; }
.cell { background: #fff; border: 1px solid var(--line); padding: 8px; min-width: 0; }
.cell.own { outline: 3px solid var(--mark); }
.cell img { width: 100%; display: block; }
.score { font-variant-numeric: tabular-nums; color: var(--muted); font-size: 12px; }
.tag { display: inline-block; font-size: 11px; padding: 1px 6px; background: var(--mark); color: #fff; margin-left: 6px; }
details { margin-top: 6px; } summary { cursor: pointer; color: var(--mark); }
.variants { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; margin-top: 8px; }
.variants figure { margin: 0; } .variants figcaption { font-size: 11px; color: var(--muted); word-break: break-all; }
.error { color: #c41011; white-space: pre-wrap; font-size: 12px; }
ul.rejected { font-size: 12px; color: var(--muted); padding-left: 18px; word-break: break-all; }
"""


def _parts(v: Variant) -> str:
    parts = " · ".join(f"{k} {p:.2f}" for k, p in v.parts.items())
    notes = f" — {', '.join(v.notes)}" if v.notes else ""
    return f"{v.total:.1f} ({parts}){notes}"


def _cell_html(cell: Cell, own: bool) -> str:
    e = html.escape
    tag = '<span class="tag">this card\'s background</span>' if own else ""
    head = f"<strong>{e(cell.background)}</strong>{tag}"
    if cell.error:
        return f'<div class="cell{" own" if own else ""}">{head}<p class="error">{e(cell.error)}</p></div>'
    chosen, others = cell.variants[0], cell.variants[1:]
    figures = "".join(
        f'<figure><img loading="lazy" src="{e(v.image)}" alt="">'
        f"<figcaption>{e(_parts(v))}<br>{e(v.key)}</figcaption></figure>"
        for v in others
    )
    rejected = "".join(f"<li>{e(k)}: {e(r)}</li>" for k, r in cell.rejected)
    return (
        f'<div class="cell{" own" if own else ""}">{head}'
        f'<img loading="lazy" src="{e(chosen.image)}" alt="">'
        f'<div class="score">chosen {e(_parts(chosen))}<br>{e(chosen.key)}</div>'
        f"<details><summary>{len(others)} other candidates</summary>"
        f'<div class="variants">{figures}</div></details>'
        f"<details><summary>{len(cell.rejected)} rejected</summary>"
        f'<ul class="rejected">{rejected}</ul></details></div>'
    )


def _card_page(card: Card, cells: list[Cell], brand: Brand) -> str:
    e = html.escape
    own = brand.field_for(card.id, card.category)
    backgrounds = brand.backgrounds(card.category)
    sections = []
    for fmt in brand.raw["formats"]:
        row = "".join(
            _cell_html(c, c.background == own)
            for bg in backgrounds
            for c in cells
            if c.fmt == fmt and c.background == bg
        )
        cols = f"repeat({len(backgrounds)}, minmax(280px, 1fr))"
        sections.append(
            f'<h3>{e(fmt)}</h3><div class="matrix" style="grid-template-columns:{cols}">{row}</div>'
        )
    return (
        f"<!doctype html><meta charset='utf-8'><title>{e(card.id)} · card preview</title>"
        f"<style>{STYLE}</style><header><a href='index.html'>← all cards</a>"
        f"<h1>{e(card.headline)}</h1><p>{e(card.id)} · {e(card.category)} · {e(card.lang)}"
        f" · own background: <strong>{e(own)}</strong></p></header><main>{''.join(sections)}</main>"
    )


def _tile(card: Card, cells: list[Cell], brand: Brand, order: int) -> dict:
    """What the index shows of one card, kept on disk so a partial run
    (--only) can rebuild the index with every other card in it."""
    own = brand.field_for(card.id, card.category)
    first = next(
        (c for c in cells if c.background == own and c.fmt == "og" and c.variants),
        None,
    )
    return {
        "order": order,
        "slug": _slug(card.id),
        "headline": card.headline,
        "category": card.category,
        "own": own,
        "image": first.variants[0].image if first else "",
        "failed": sum(1 for c in cells if c.error),
    }


def _index_page(tiles: list[dict], problems: list[str], brand: Brand) -> str:
    e = html.escape
    missing = "".join(f"<li class='error'>{e(p)}</li>" for p in problems)
    missing = f"<h2>Pages without a card</h2><ul>{missing}</ul>" if problems else ""
    html_tiles = []
    for tile in tiles:
        img = (
            f'<img loading="lazy" src="{e(tile["image"])}" alt="">'
            if tile["image"]
            else ""
        )
        warn = (
            f" · <span class='error'>{tile['failed']} without a design</span>"
            if tile["failed"]
            else ""
        )
        html_tiles.append(
            f'<a href="{e(tile["slug"])}.html">{img}<strong>{e(tile["headline"])}</strong>'
            f"<p>{e(tile['category'])} · {e(tile['own'])}{warn}</p></a>"
        )
    return (
        f"<!doctype html><meta charset='utf-8'><title>Social card preview</title>"
        f"<style>{STYLE}</style><header><h1>Social card preview</h1>"
        f"<p>{len(tiles)} cards, each on every background its category draws from, in "
        f"{len(brand.raw['formats'])} formats. Each tile shows the card on its own background in og.</p>"
        f"</header><main>{missing}<div class='index'>{''.join(html_tiles)}</div></main>"
    )


def build(
    cards: list[Card],
    order: dict[str, int],
    problems: list[str],
    brand: Brand,
    *,
    partial: bool,
) -> Path:
    """Design and save every cell of `cards`. A partial run replaces only
    those cards and keeps the rest of the gallery."""
    if partial:
        for card in cards:
            shutil.rmtree(OUT_DIR / "img" / _slug(card.id), ignore_errors=True)
    elif OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    (OUT_DIR / "data").mkdir(parents=True, exist_ok=True)
    jobs = [
        (card, bg, fmt)
        for card in cards
        for bg in brand.backgrounds(card.category)
        for fmt in brand.raw["formats"]
    ]
    with ProcessPoolExecutor() as pool:
        cells = list(pool.map(preview_cell, *zip(*jobs, strict=True), chunksize=1))
    for card in cards:
        mine = [c for c in cells if c.card_id == card.id]
        slug = _slug(card.id)
        (OUT_DIR / f"{slug}.html").write_text(
            _card_page(card, mine, brand), encoding="utf-8"
        )
        tile = _tile(card, mine, brand, order[card.id])
        (OUT_DIR / "data" / f"{slug}.json").write_text(
            json.dumps(tile), encoding="utf-8"
        )
    tiles = sorted(
        (
            json.loads(f.read_text(encoding="utf-8"))
            for f in (OUT_DIR / "data").glob("*.json")
        ),
        key=lambda tile: tile["order"],
    )
    index = OUT_DIR / "index.html"
    index.write_text(_index_page(tiles, problems, brand), encoding="utf-8")
    return index


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--only", help="comma-separated card ids to preview")
    args = parser.parse_args()
    brand = load_brand()
    cards, problems = sample_cards(brand)
    if args.only:
        wanted = set(args.only.split(","))
        unknown = wanted - {c.id for c in cards}
        if unknown:
            print(f"unknown card ids: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
    order = {card.id: i for i, card in enumerate(cards)}
    if args.only:
        cards = [c for c in cards if c.id in wanted]
    for problem in problems:
        print(f"no card: {problem}", file=sys.stderr)
    index = build(cards, order, problems, brand, partial=bool(args.only))
    print(index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
