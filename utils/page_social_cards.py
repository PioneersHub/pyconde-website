"""Generate the social card of every site page that can carry one.

Which pages, and from which fields, is configured in
``utils/social_cards/pages.yaml``: one recipe per Lektor page model (blog
posts, masterclasses, call pages, …). Each recipe fixes the card category
and with it the visual family, so a blog post never looks like a
masterclass. A card is written next to its page as ``social_card.png`` and
linked through the page's ``social_card_image`` field.

Every generated PNG carries a record of exactly what is printed on it plus a
checksum of its pixels (see :func:`card_record`). The record decides two
things:

- **Redraws.** A card is redrawn only when its record differs from what the
  page and branding.yaml say now, or when brand.yaml changed. Other edits to
  a page leave its card alone.
- **Ownership.** A PNG without the record, or whose pixels no longer match
  it, was not drawn here or was changed since. It is a hand-made card and is
  never overwritten, whatever it is called. A page whose
  ``social_card_image`` points anywhere else is never touched either.

A page that cannot get a card (missing field, a date that contradicts
branding.yaml, no design passing the brand checks) is reported as failed;
the other pages are still processed, and the run exits non-zero.
"""

import hashlib
import sys
from configparser import RawConfigParser
from functools import cache
from pathlib import Path
from typing import Any

import lektor_lr
import yaml
from social_cards.brand import REPO_ROOT, Brand, load_brand, spec_fingerprint
from social_cards.composition import Composition
from social_cards.content import Card, CardContentError, Speaker, sponsor_logo_path
from social_cards.pipeline import NoValidDesignError, design, export
from social_cards.render import read_card_record

CONTENT_DIR = REPO_ROOT / "content"
MODELS_DIR = REPO_ROOT / "models"
CONFIG_PATH = Path(__file__).with_name("social_cards") / "pages.yaml"
CARD_NAME = "social_card.png"
FORMAT = "og"


class PageCardError(ValueError):
    """A page lacks what its card needs, or contradicts branding.yaml."""


def load_config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


@cache
def _model_ini(model: str) -> RawConfigParser | None:
    path = MODELS_DIR / f"{model}.ini"
    if not path.is_file():
        return None
    ini = RawConfigParser(interpolation=None)
    ini.read(path, encoding="utf-8")
    return ini


def has_card_field(model: str) -> bool:
    ini = _model_ini(model)
    return ini is not None and ini.has_section("fields.social_card_image")


def resolve_model(page_dir: Path, root: Path) -> str | None:
    """The page's model as Lektor resolves it: its own ``_model``, else the
    parent model's default child model, else a model named like the page."""
    lr = page_dir / "contents.lr"
    if lr.is_file():
        _, fields = lektor_lr.read_lr(lr)
        explicit = lektor_lr.field_value(fields, "_model")
        if explicit:
            return explicit.strip()
    if page_dir != root:
        parent = resolve_model(page_dir.parent, root)
        ini = _model_ini(parent) if parent else None
        if ini is not None and ini.has_option("children", "model"):
            return ini.get("children", "model")
    return page_dir.name if _model_ini(page_dir.name) else None


def card_url(page_dir: Path, root: Path) -> str:
    rel = page_dir.relative_to(root).as_posix()
    return f"/{rel}/{CARD_NAME}" if rel != "." else f"/{CARD_NAME}"


def _value(fields: list[lektor_lr.Field], name: str, slug: str) -> str:
    value = (lektor_lr.field_value(fields, name) or "").strip()
    if not value:
        raise PageCardError(f"{slug}: missing field {name}")
    return value


def _kicker(
    slug: str,
    fields: list[lektor_lr.Field],
    recipe: dict[str, Any],
    lang: str,
    brand: Brand,
) -> str | None:
    """A page field verbatim (`kicker`), or a field's value looked up in the
    category's table (`kicker_from`), or the category label."""
    if "kicker" in recipe:
        return _value(fields, recipe["kicker"], slug)
    if "kicker_from" not in recipe:
        return None
    source = recipe["kicker_from"]
    table = brand.category(recipe["category"])[f"kicker_by_{source}"]
    value = _value(fields, source, slug)
    if value not in table:
        raise PageCardError(
            f"{slug}: {source} {value!r} is not one of {', '.join(table)}"
        )
    return table[value][lang]


def _headline(
    slug: str, fields: list[lektor_lr.Field], recipe: dict[str, Any], lang: str
) -> str:
    """A page field (`headline`) or the recipe's fixed text (`headline_text`)."""
    if "headline_text" in recipe:
        if lang not in recipe["headline_text"]:
            raise PageCardError(f"{slug}: pages.yaml has no headline_text in {lang}")
        return recipe["headline_text"][lang]
    return _value(fields, recipe["headline"], slug)


def _sponsor_logo(
    slug: str,
    fields: list[lektor_lr.Field],
    recipe: dict[str, Any],
    config: dict[str, Any],
    brand: Brand,
) -> Path | None:
    """The logo file behind the page's site path (e.g. /static/…)."""
    if "sponsor_logo" not in recipe:
        return None
    url = _value(fields, recipe["sponsor_logo"], slug)
    path = REPO_ROOT / config["site_root"] / url.lstrip("/")
    if not path.is_file():
        raise PageCardError(f"{slug}: sponsor logo not found: {path}")
    try:
        return sponsor_logo_path(slug, recipe["category"], path, brand)
    except CardContentError as err:
        raise PageCardError(str(err)) from None


def page_card(
    slug: str,
    fields: list[lektor_lr.Field],
    model: str,
    config: dict[str, Any],
    brand: Brand,
) -> Card:
    """The card the model's recipe in pages.yaml makes of one page."""
    recipe = config["recipes"][model]
    lang = config["page_lang"].get(slug, "en")
    event = recipe.get("event", "conference")
    if "day_field" in recipe:
        day = brand.event_dates(lang, event)
        if day not in _value(fields, recipe["day_field"], slug):
            raise PageCardError(
                f"{slug}: {recipe['day_field']} does not name {day}, the {event} day in databags/branding.yaml"
            )
    speakers: tuple[Speaker, ...] = ()
    if "speakers" in recipe:
        names = _value(fields, recipe["speakers"], slug).split(" & ")
        speakers = tuple(Speaker(name=n.strip()) for n in names)
    return Card(
        id=slug,
        category=recipe["category"],
        lang=lang,
        headline=_headline(slug, fields, recipe, lang),
        formats=(FORMAT,),
        kicker=_kicker(slug, fields, recipe, lang, brand),
        speakers=speakers,
        event=event,
        sponsor_logo=_sponsor_logo(slug, fields, recipe, config, brand),
    )


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def card_record(card: Card, brand: Brand) -> dict[str, str]:
    """Everything printed on the card, plus the brand spec it was drawn
    under. Nothing else on the page influences the card."""
    return {
        "category": card.category,
        "headline": card.headline,
        "speakers": card.speaker_line,
        "kicker": card.kicker_text(brand),
        "date": brand.event_dates(card.lang, card.event),
        "venue": brand.event.venue,
        "event": brand.event.name,
        "spec": spec_fingerprint(),
        "sponsor_logo": _file_digest(card.sponsor_logo) if card.sponsor_logo else "",
    }


def pages(
    root: Path, config: dict[str, Any], *, preview: bool = False
) -> list[tuple[Path, str]]:
    """(page folder, model) for every page with a recipe. Models listed in
    `preview_only` are included only for the preview gallery."""
    skipped = set(config["skip_models"])
    if not preview:
        skipped |= set(config["preview_only"])
    found = []
    for lr in sorted(root.rglob("contents.lr")):
        rel = lr.parent.relative_to(root)
        if rel.parts and rel.parts[0] in config["skip_dirs"]:
            continue
        model = resolve_model(lr.parent, root)
        if model and model not in skipped and model in config["recipes"]:
            if not has_card_field(model):
                raise PageCardError(
                    f"pages.yaml has a recipe for {model}, but models/{model}.ini has no social_card_image field"
                )
            found.append((lr.parent, model))
    return found


def card_for(
    page_dir: Path,
    model: str,
    root: Path,
    config: dict[str, Any],
    brand: Brand,
) -> Card:
    """The card of one page, as its recipe in pages.yaml makes it."""
    _, fields = lektor_lr.read_lr(page_dir / "contents.lr")
    slug = page_dir.relative_to(root).as_posix()
    return page_card(slug, fields, model, config, brand)


def update_page(
    page_dir: Path,
    model: str,
    root: Path,
    config: dict[str, Any],
    history: list[Composition],
) -> str:
    """Bring one page's card up to date; returns what happened."""
    brand = load_brand()
    lr = page_dir / "contents.lr"
    text, fields = lektor_lr.read_lr(lr)
    slug = page_dir.relative_to(root).as_posix()
    url = card_url(page_dir, root)
    png = page_dir / CARD_NAME
    linked = (lektor_lr.field_value(fields, "social_card_image") or "").strip()

    # Hand-made cards are never touched.
    if linked and linked != url:
        return f"kept: social_card_image points to {linked}"
    stored = read_card_record(png) if png.exists() else None
    if png.exists() and stored is None:
        return f"kept: {CARD_NAME} is hand-made or was edited by hand"

    # A page that has to be linked must be writable before anything is drawn.
    if linked != url and not lektor_lr.round_trip_ok(text, fields):
        raise PageCardError(
            f"{slug}: contents.lr does not round-trip through lektor_lr "
            "(often a missing final newline); fix the file, then run again"
        )
    card = card_for(page_dir, model, root, config, brand)
    record = card_record(card, brand)
    if stored == record:
        what = "up to date"
    else:
        result = design(card, FORMAT, brand, history)
        export(result, brand, png, record)
        history.append(result.chosen.comp)
        changed = [key for key in record if stored and stored.get(key) != record[key]]
        what = f"redrawn: {', '.join(changed)} changed" if stored else "drawn"
    if linked != url:
        lektor_lr.write_lr(
            lr, lektor_lr.upsert_fields(fields, {"social_card_image": url})
        )
        what += f", linked as {url}"
    return what


def generate(root: Path = CONTENT_DIR) -> dict[str, str]:
    """Bring every page card up to date; returns {page: what happened}."""
    config = load_config()
    history: list[Composition] = []
    outcome = {}
    for page_dir, model in pages(root, config):
        slug = page_dir.relative_to(root).as_posix()
        try:
            outcome[slug] = update_page(page_dir, model, root, config, history)
        except (PageCardError, CardContentError, NoValidDesignError) as err:
            outcome[slug] = f"failed: {str(err).splitlines()[0]}"
    return outcome


def main() -> int:
    outcome = generate()
    for slug, what in outcome.items():
        print(f"{slug}: {what}")
    failed = [slug for slug, what in outcome.items() if what.startswith("failed")]
    if failed:
        print(f"{len(failed)} page(s) got no card", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
