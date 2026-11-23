"""The social-card engine: brand spec, typesetting, validation, pipeline.

The validator is tested by breaking a known-good composition one rule at a
time, so each check is shown to reject exactly what it is meant to. The
fixture set in tests/social_cards/cards.yaml is rendered in every format it
lists: a regression there means some real card no longer has a compliant
design.

Needs the `cards` extra: uv run --extra cards pytest
"""

from __future__ import annotations

import io
import json
import re
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo

pytest.importorskip(
    "uharfbuzz", reason="the social-card engine needs: uv run --extra cards pytest"
)

import page_social_cards as pc  # noqa: E402
import social_card_img_gen  # noqa: E402
from social_cards.brand import REPO_ROOT, BrandSpecError, contrast, load_brand  # noqa: E402
from social_cards.composition import Box, Composition, Logo, Text  # noqa: E402
from social_cards.content import (  # noqa: E402
    CardContentError,
    analyse,  # noqa: E402
    card_from_dict,
    load_cards,
)
from social_cards.layouts import STRATEGIES, Context  # noqa: E402
from social_cards.pipeline import NoValidDesignError, design  # noqa: E402
from social_cards.render import render  # noqa: E402
from social_cards.typeset import Frame, set_best, set_block, style_for, tokenize  # noqa: E402
from social_cards.validate import validate  # noqa: E402

FIXTURES = Path(__file__).parent / "social_cards" / "cards.yaml"
# Every fixture card must reach this critique score (of 100).
MIN_SCORE = 75


@pytest.fixture(scope="module")
def brand():
    return load_brand()


@pytest.fixture(scope="module")
def cards(brand):
    return {c.id: c for c in load_cards(FIXTURES, brand)}


def rules(violations) -> set[str]:
    return {v.rule for v in violations}


# ── brand spec ───────────────────────────────────────────────


def test_palette_matches_website_css(brand):
    css = (REPO_ROOT / "assets/static/css/main.css").read_text()
    root = css[css.index(":root {") : css.index("}", css.index(":root {"))]
    defined = dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", root))
    for name, token in brand.raw["css_tokens"].items():
        assert defined[token].lower() == brand.palette[name].lower(), name


def test_event_facts_come_from_branding_yaml(brand):
    assert brand.event.name == "PyCon DE 2027"
    assert brand.event_dates("en") == "20–22 April 2027"
    assert brand.event_dates("de") == "20.–22. April 2027"
    assert brand.event.venue == "HCC Heidelberg"


def test_every_field_text_pair_clears_the_contrast_floor(brand):
    floor = brand.raw["min_text_contrast"]
    for name, field in brand.raw["fields"].items():
        assert contrast(brand.color(field["text"]), brand.color(name)) >= floor, name


# ── typesetting ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "unit"),
    [
        ("Writing extensions with PyO3 0.22 and nanobind", "PyO3 0.22"),
        ("lessons from moving 40 TB a day", "40 TB"),
        ("Python 3.14 – what is new", "3.14 –"),
    ],
)
def test_tokenize_keeps_units_together(text, unit):
    assert any(unit in u for u in tokenize(text))


def test_breaker_never_ends_a_line_on_a_weak_word(brand):
    fmt = brand.format("og")
    style = style_for(brand, fmt, "headline", 60)
    block = set_block(
        brand,
        "Building reliable tools for the data science community in Heidelberg",
        style,
        Frame(620, None, 5),
    )
    weak = {w.lower() for w in brand.raw["line_breaking"]["weak_line_endings"]}
    for line in block.lines[:-1]:
        assert line.text.split()[-1].lower() not in weak, block.text


def test_long_single_word_last_line_is_not_an_orphan(brand):
    style = style_for(brand, brand.format("og"), "headline", 116)
    block = set_block(brand, "Rust for Python Developers", style, Frame(1000, None, 3))
    assert block.text == "Rust for Python\nDevelopers"
    assert "single-word last line" not in block.issues


def test_speaker_names_never_break_inside(brand):
    names = [
        "Dr. Johanna Müller-Lüdenscheidt,",
        "Emre Yılmaz,",
        "Anna-Lena Groß,",
        "Kai Bauer",
    ]
    for block in set_best(
        brand, brand.format("og"), "speaker", names, Frame(420, 400, 0)
    ):
        for line in block.lines:
            # every line is a run of whole names
            assert all(
                part.strip() in " ".join(names) for part in line.text.split(", ")
            )
            assert not line.text.endswith(("Dr.", "Johanna", "Emre", "Anna-Lena"))


def test_optical_alignment_puts_ink_on_the_margin(brand):
    style = style_for(brand, brand.format("og"), "headline", 92)
    block = set_block(brand, "Typing at scale", style, Frame(1000))
    run, offset = block.lines[0], block.offsets[0]
    assert run.ink_left + offset == pytest.approx(0.0)


# ── validation ───────────────────────────────────────────────


@pytest.fixture(scope="module")
def good(brand, cards) -> tuple[Composition, object]:
    card = cards["cfp-en"]
    ctx = Context(brand, brand.format("og"), card, analyse(card))
    comp = STRATEGIES["field"].build(
        ctx,
        {
            "field": "blue",
            "logo": "corner_bottom",
            "anchor": "top",
            "measure": 1.0,
            "size_shift": 0,
        },
    )
    assert validate(comp, brand, card) == []
    return comp, card


def _swap(comp: Composition, old, new) -> Composition:
    return replace(comp, elements=[new if e is old else e for e in comp.elements])


def test_rejects_unapproved_text_colour(brand, good):
    comp, card = good
    hl = comp.text("headline")
    assert "color-pair" in rules(
        validate(_swap(comp, hl, replace(hl, color="green")), brand, card)
    )


def test_rejects_forbidden_naming(brand, good):
    comp, card = good
    hl = comp.text("headline")
    style = hl.block.style
    bad = replace(
        hl, block=replace(hl.block, lines=(style.shape("PyCon DE & PyData 2027"),))
    )
    assert {"copy", "content-altered"} <= rules(
        validate(_swap(comp, hl, bad), brand, card)
    )


def test_rejects_distorted_logo(brand, good):
    comp, card = good
    lg: Logo = comp.logos[0]
    stretched = replace(lg, box=Box(lg.box.x, lg.box.y, lg.box.w * 1.1, lg.box.h))
    assert "logo-distortion" in rules(validate(_swap(comp, lg, stretched), brand, card))


def test_rejects_recoloured_logo(brand, good):
    comp, card = good
    lg: Logo = comp.logos[0]
    assert "logo" in rules(
        validate(_swap(comp, lg, replace(lg, color="orange")), brand, card)
    )


def test_rejects_text_outside_the_safe_area(brand, good):
    comp, card = good
    hl = comp.text("headline")
    assert "safe-area" in rules(
        validate(_swap(comp, hl, replace(hl, x=10)), brand, card)
    )


def test_rejects_collisions(brand, good):
    comp, card = good
    hl = comp.text("headline")
    lg = comp.logos[0]
    moved = replace(hl, x=lg.box.x - 20, y=lg.box.y + 10)
    assert "collision" in rules(validate(_swap(comp, hl, moved), brand, card))


def test_rejects_tiny_text(brand, good):
    comp, card = good
    k = comp.text("kicker")
    tiny = replace(k.block, style=replace(k.block.style, size=9))
    assert "tiny-text" in rules(
        validate(_swap(comp, k, replace(k, block=tiny)), brand, card)
    )


def test_rejects_wrong_event_facts(brand, good):
    comp, card = good
    facts: Text = comp.text("event_facts")
    style = facts.block.style
    wrong = replace(facts.block, lines=(style.shape("14–17 April 2026 · Darmstadt"),))
    assert {"event-facts", "copy"} <= rules(
        validate(_swap(comp, facts, replace(facts, block=wrong)), brand, card)
    )


# ── content ──────────────────────────────────────────────────


def test_missing_required_field_is_an_error(brand):
    with pytest.raises(CardContentError, match="lang"):
        card_from_dict(
            {"id": "x", "category": "news", "headline": "Hi", "formats": ["og"]}, brand
        )


def test_unknown_category_is_an_error(brand):
    with pytest.raises(BrandSpecError, match="unknown category"):
        card_from_dict(
            {
                "id": "x",
                "category": "party",
                "lang": "en",
                "headline": "Hi",
                "formats": ["og"],
            },
            brand,
        )


def test_kicker_is_dropped_when_it_repeats_the_headline(brand, cards):
    assert cards["dates-en"].kicker_text(brand) == ""


# ── pipeline ─────────────────────────────────────────────────


def _fixture_cases():
    brand = load_brand()
    return [(c.id, fmt) for c in load_cards(FIXTURES, brand) for fmt in c.formats]


@pytest.mark.parametrize(("card_id", "fmt"), _fixture_cases())
def test_every_fixture_card_gets_a_valid_design(brand, cards, card_id, fmt):
    result = design(cards[card_id], fmt, brand)
    assert validate(result.chosen.comp, brand, cards[card_id]) == []
    assert result.chosen.score.total > MIN_SCORE


def test_design_is_deterministic(brand, cards):
    first = render(design(cards["talk-cpp"], "og", brand).chosen.comp, brand)
    second = render(design(cards["talk-cpp"], "og", brand).chosen.comp, brand)
    a, b = io.BytesIO(), io.BytesIO()
    first.save(a, "PNG")
    second.save(b, "PNG")
    assert a.getvalue() == b.getvalue()


def test_export_has_the_og_contract_size(brand, cards):
    image = render(design(cards["news-short"], "og", brand).chosen.comp, brand)
    assert image.size == (2400, 1260)  # 1200×630 og:image at 2×


def test_low_resolution_photo_is_never_published(brand):
    card = card_from_dict(
        {
            "id": "small-photo",
            "category": "community",
            "lang": "en",
            "headline": "Meet the community",
            "image": "assets/static/media/keynotes/hilde-kuehne.jpg",  # 400×400
            "formats": ["og"],
        },
        brand,
    )
    with pytest.raises(NoValidDesignError, match="photo"):
        design(card, "og", brand)


def test_talk_cards_are_only_redrawn_when_their_content_changes(tmp_path):
    talks = json.loads((REPO_ROOT / "databags/talks-2026.json").read_text())["talks"][
        :2
    ]
    assert social_card_img_gen.generate(talks, tmp_path) == [t["code"] for t in talks]
    assert social_card_img_gen.generate(talks, tmp_path) == []
    talks[0] = {**talks[0], "title": talks[0]["title"] + " (updated)"}
    assert social_card_img_gen.generate(talks, tmp_path) == [talks[0]["code"]]


# ── content families ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("category", "strategy", "field"),
    [
        ("talk", "spine", "white"),
        ("masterclass", "field", "orange"),
        ("news", "python", "blue"),
        ("page", "field", "blue"),
    ],
)
def test_each_content_family_keeps_its_signature(brand, category, strategy, field):
    card = card_from_dict(
        {
            "id": f"family-{category}",
            "category": category,
            "lang": "en",
            "headline": "Typing at scale",
            "formats": ["og"],
        },
        brand,
    )
    for fmt in ("og", "square"):
        ranking = design(card, fmt, brand).ranking
        assert {(c.comp.strategy, c.comp.field) for c in ranking} == {(strategy, field)}
    if category == "page":
        assert {c.comp.params["logo"] for c in ranking} <= {"column", "top"}


# ── page cards ───────────────────────────────────────────────

RUST = "masterclasses/rust-for-python-developers-rodrigo-girao-serrao"
RUST_URL = f"/{RUST}/social_card.png"
POST = "blog/t-shirt-sizes"


@pytest.fixture
def content_root(tmp_path) -> Path:
    """Copies of a real masterclass page and a real blog post, without cards.
    The blog index is copied too: blog posts take their model from it."""
    root = tmp_path / "content"
    for page in (RUST, POST):
        shutil.copytree(pc.CONTENT_DIR / page, root / page)
        (root / page / pc.CARD_NAME).unlink(missing_ok=True)
        lr = root / page / "contents.lr"
        lr.write_text(re.sub(r"\n---\nsocial_card_image: [^\n]*", "", lr.read_text()))
    shutil.copy(pc.CONTENT_DIR / "blog" / "contents.lr", root / "blog" / "contents.lr")
    return root


def _edit(root: Path, page: str, old: str, new: str) -> None:
    lr = root / page / "contents.lr"
    text = lr.read_text()
    assert old in text
    lr.write_text(text.replace(old, new, 1))


def _hand_made(path: Path) -> bytes:
    """A PNG without the generator's record, as a designer would export it."""
    out = io.BytesIO()
    Image.new("RGB", (1200, 630), "#3778be").save(out, "PNG")
    path.write_bytes(out.getvalue())
    return out.getvalue()


def test_page_cards_are_drawn_and_linked(content_root):
    lr = content_root / RUST / "contents.lr"
    before = lr.read_text()
    assert pc.generate(content_root) == {
        POST: f"drawn, linked as /{POST}/social_card.png",
        RUST: f"drawn, linked as {RUST_URL}",
    }
    # The page gains exactly one field; nothing else in it changes.
    assert (
        lr.read_text()
        == before.rstrip("\n") + f"\n---\nsocial_card_image: {RUST_URL}\n"
    )


def test_blog_post_takes_its_model_from_the_blog_index(content_root):
    assert pc.resolve_model(content_root / POST, content_root) == "blog-post"
    pc.generate(content_root)
    assert pc.read_card_record(content_root / POST / pc.CARD_NAME)["category"] == "news"


def test_unchanged_card_is_not_rewritten(content_root):
    pc.generate(content_root)
    png = content_root / RUST / pc.CARD_NAME
    stamp = png.stat().st_mtime_ns
    assert pc.generate(content_root)[RUST] == "up to date"
    assert png.stat().st_mtime_ns == stamp


def test_edits_off_the_card_do_not_redraw_it(content_root):
    pc.generate(content_root)
    _edit(
        content_root, RUST, "9:00–16:00", "9:30–16:30"
    )  # time of day is not on the card
    _edit(content_root, RUST, "tags:\n", "tags:\n\nNewTag\n")
    assert pc.generate(content_root)[RUST] == "up to date"


@pytest.mark.parametrize(
    ("old", "new", "changed", "printed"),
    [
        (
            "title: Rust for Python Developers",
            "title: Rust for Pythonistas",
            "headline",
            "Rust for Pythonistas",
        ),
        (
            "trainer: Rodrigo Girão Serrão",
            "trainer: Rodrigo Girão Serrão & Ada Lindqvist",
            "speakers",
            "Rodrigo Girão Serrão, Ada Lindqvist",
        ),
        ("hours: 6", "hours: 3", "kicker", "Half-Day Masterclass"),
    ],
)
def test_changes_on_the_card_redraw_it(content_root, old, new, changed, printed):
    pc.generate(content_root)
    _edit(content_root, RUST, old, new)
    assert pc.generate(content_root)[RUST] == f"redrawn: {changed} changed"
    assert pc.read_card_record(content_root / RUST / pc.CARD_NAME)[changed] == printed


def test_brand_spec_change_redraws_cards(content_root, monkeypatch):
    pc.generate(content_root)
    monkeypatch.setattr(pc, "spec_fingerprint", lambda: "new-spec")
    assert set(pc.generate(content_root).values()) == {"redrawn: spec changed"}


def test_masterclass_card_shows_the_masterclass_day(brand, content_root):
    _, fields = pc.lektor_lr.read_lr(content_root / RUST / "contents.lr")
    card = pc.page_card(
        RUST, fields, pc.load_config()["recipes"]["masterclass"], "en", brand
    )
    facts = design(card, "og", brand).chosen.comp.text("event_facts").block.text
    assert "19 April 2027" in facts
    assert "20–22" not in facts
    assert card.kicker == "Full-Day Masterclass"


def test_page_contradicting_branding_gets_no_card(content_root):
    _edit(content_root, RUST, "19 April 2027", "18 April 2027")
    outcome = pc.generate(content_root)
    assert outcome[RUST].startswith("failed:") and "masterclasses day" in outcome[RUST]
    assert not (content_root / RUST / pc.CARD_NAME).exists()
    assert outcome[POST].startswith("drawn")  # one bad page does not block the others


def test_unknown_hours_gets_no_card(content_root):
    _edit(content_root, RUST, "hours: 6", "hours: 4")
    assert pc.generate(content_root)[RUST].startswith("failed: ")


def test_unwritable_page_gets_no_card_file(content_root):
    lr = content_root / POST / "contents.lr"
    lr.write_text(lr.read_text().rstrip("\n"))  # no final newline: does not round-trip
    assert "round-trip" in pc.generate(content_root)[POST]
    assert not (content_root / POST / pc.CARD_NAME).exists()


# ── hand-made cards are never replaced ───────────────────────


def test_card_linked_under_another_path_is_kept(content_root):
    lr = content_root / RUST / "contents.lr"
    lr.write_text(
        lr.read_text().rstrip("\n") + f"\n---\nsocial_card_image: /{RUST}/card-v2.png\n"
    )
    assert (
        pc.generate(content_root)[RUST]
        == f"kept: social_card_image points to /{RUST}/card-v2.png"
    )
    assert not (content_root / RUST / pc.CARD_NAME).exists()


def test_generated_card_replaced_by_a_hand_made_one_is_kept(content_root):
    """Procedure A: overwrite the generated social_card.png with your own file."""
    pc.generate(content_root)
    png = content_root / RUST / pc.CARD_NAME
    original = _hand_made(png)
    _edit(
        content_root,
        RUST,
        "title: Rust for Python Developers",
        "title: Rust for Pythonistas",
    )
    assert (
        pc.generate(content_root)[RUST]
        == "kept: social_card.png is hand-made or was edited by hand"
    )
    assert png.read_bytes() == original


def test_generated_card_edited_in_place_is_kept(content_root):
    """An editor that keeps the PNG metadata still cannot fool the generator:
    the pixels no longer match the stored checksum."""
    pc.generate(content_root)
    png = content_root / RUST / pc.CARD_NAME
    with Image.open(png) as im:
        info = PngInfo()
        for key, value in im.text.items():
            info.add_text(key, value)
        edited = im.convert("RGB")
    ImageDraw.Draw(edited).rectangle((0, 0, 200, 200), fill="#fac800")
    edited.save(png, "PNG", pnginfo=info)
    original = png.read_bytes()
    _edit(
        content_root,
        RUST,
        "title: Rust for Python Developers",
        "title: Rust for Pythonistas",
    )
    assert (
        pc.generate(content_root)[RUST]
        == "kept: social_card.png is hand-made or was edited by hand"
    )
    assert png.read_bytes() == original


def test_generated_card_replaced_under_another_name_is_kept(content_root):
    """Procedure B: new file name, page points to it, generated file deleted."""
    pc.generate(content_root)
    lr = content_root / RUST / "contents.lr"
    _hand_made(content_root / RUST / "card.png")
    (content_root / RUST / pc.CARD_NAME).unlink()
    lr.write_text(lr.read_text().replace(RUST_URL, f"/{RUST}/card.png"))
    _edit(
        content_root,
        RUST,
        "title: Rust for Python Developers",
        "title: Rust for Pythonistas",
    )
    assert (
        pc.generate(content_root)[RUST]
        == f"kept: social_card_image points to /{RUST}/card.png"
    )
    assert not (content_root / RUST / pc.CARD_NAME).exists()


def test_unlinked_hand_made_card_is_neither_overwritten_nor_linked(content_root):
    png = content_root / POST / pc.CARD_NAME
    original = _hand_made(png)
    assert (
        pc.generate(content_root)[POST]
        == "kept: social_card.png is hand-made or was edited by hand"
    )
    assert png.read_bytes() == original
    assert "social_card_image" not in (content_root / POST / "contents.lr").read_text()


def test_every_existing_card_in_the_repo_is_classified():
    """Snapshot of the real site: each card file is either one the generator
    drew (and could redraw) or hand-made (and must be kept)."""
    for png in pc.CONTENT_DIR.rglob(pc.CARD_NAME):
        if "archive" in png.parts:
            continue
        record = pc.read_card_record(png)
        assert record is None or record["category"] in pc.load_brand().raw["categories"]
