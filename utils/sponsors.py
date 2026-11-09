import re
import sys
from collections import Counter
from pathlib import Path
from string import Template
from urllib.parse import urlsplit

import yaml


def validate_unique_ids(sponsor_types):
    """Check that all sponsor ids are unique across all types. Exit with error if not."""
    seen = []
    for sponsor_type in sponsor_types:
        for sponsor in sponsor_type.get("sponsors", []):
            seen.append((sponsor["id"], sponsor["name"], sponsor_type["name"]))

    id_counts = Counter(entry[0] for entry in seen)
    duplicates = {id_ for id_, count in id_counts.items() if count > 1}

    if duplicates:
        print("ERROR: Duplicate sponsor ids found in databags/sponsors.yaml:")
        for id_, name, type_name in seen:
            if id_ in duplicates:
                print(f"  id='{id_}' name='{name}' (in {type_name})")
        sys.exit(1)


LOGO_SIZES = {"xl", "lg", "md", "sm"}


def tier_layout_errors(sponsor_types):
    """Each tier renders either as a sized logo row or inside a labelled group."""
    errors = []
    for sponsor_type in sponsor_types:
        group = sponsor_type.get("group")
        logo_size = sponsor_type.get("logo_size")
        if "group" in sponsor_type and not (isinstance(group, str) and group.strip()):
            errors.append(
                f"type '{sponsor_type['id']}' has an empty 'group'; it is the divider label"
            )
        elif (group is not None) == (logo_size is not None):
            errors.append(
                f"type '{sponsor_type['id']}' needs exactly one of 'group' or 'logo_size'"
            )
        elif logo_size is not None and logo_size not in LOGO_SIZES:
            errors.append(
                f"type '{sponsor_type['id']}' has logo_size '{logo_size}', expected one of {sorted(LOGO_SIZES)}"
            )
    return errors


def past_editions_errors(past_editions):
    """The moving line needs its lineups, and every id or tier it refers to."""
    if (
        not past_editions
        or not past_editions.get("title")
        or not past_editions.get("bags")
    ):
        return ["'past_editions' needs a 'title' and a non-empty 'bags' list"]

    errors = []
    past_ids = set()
    past_tier_ids = set()
    for bag_name in past_editions["bags"]:
        bag_path = Path(__file__).parents[1] / f"databags/{bag_name}.yaml"
        if not bag_path.is_file():
            errors.append(
                f"past_editions bag 'databags/{bag_name}.yaml' does not exist"
            )
            continue
        with bag_path.open() as f:
            past_data = yaml.load(f, Loader=yaml.SafeLoader)
        past_tier_ids |= {t["id"] for t in past_data["types"]}
        past_ids |= {s["id"] for t in past_data["types"] for s in t.get("sponsors", [])}

    for key in ("tonal_logos", "featured"):
        errors += [
            f"past_editions {key} id '{logo_id}' is not in any past lineup"
            for logo_id in past_editions.get(key, [])
            if logo_id not in past_ids
        ]
    # The template ranks every past sponsor by its tier's position here.
    missing_tiers = past_tier_ids - set(past_editions.get("tier_order", []))
    if missing_tiers:
        errors.append(
            f"past_editions tier_order is missing tier ids {sorted(missing_tiers)}"
        )
    return errors


def validate_presentation(data):
    """The sponsor wall template needs every tier's layout and every past lineup.

    Jinja renders a missing value as nothing, so a typo here would silently drop
    or misplace logos on the page; catch it before build instead.
    """
    errors = tier_layout_errors(data["types"]) + past_editions_errors(
        data.get("past_editions")
    )
    if errors:
        print("ERROR: Invalid sponsor wall configuration in databags/sponsors.yaml:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)


# Profile hosts a sponsor's `social` links may point to, and the link text
# shown for each on the sponsor page.
SOCIAL_PLATFORMS = {"instagram.com": "Instagram", "linkedin.com": "LinkedIn"}


def social_platform(url):
    """Name of the platform a profile URL is on, or None for an unknown host."""
    host = (urlsplit(url).hostname or "").removeprefix("www.")
    return SOCIAL_PLATFORMS.get(host)


def validate_social_links(sponsor_types):
    """The page labels each link by its platform, so every host must be known."""
    errors = [
        f"sponsor '{sponsor['id']}' social link {url} is not on one of {sorted(SOCIAL_PLATFORMS)}"
        for sponsor_type in sponsor_types
        for sponsor in sponsor_type.get("sponsors", [])
        for url in sponsor.get("social", [])
        if social_platform(url) is None
    ]
    if errors:
        print("ERROR: Unknown social links in databags/sponsors.yaml:")
        for error in errors:
            print(f"  {error}")
        print("  Add the platform to SOCIAL_PLATFORMS in utils/sponsors.py.")
        sys.exit(1)


PARAGRAPH_BREAK = re.compile(r"(?:<br\s*/?>\s*){2,}")


def as_paragraphs(description):
    """Turn the `<br/><br/>` breaks used in sponsors.yaml into blank lines.

    The page renders the description as Markdown, so a blank line becomes a
    real paragraph with the site's spacing; the doubled <br/> tags only add
    uneven gaps on top of (or instead of) that.
    """
    return PARAGRAPH_BREAK.sub("\n\n", description).strip()


def dict_to_lektor(sponsor):
    tmpl = Template("""name: $name
---
id: $id
---
type: $type
---
type_id: $type_id
---
title: $title
---
full_description: $full_description
---
logo: $logo
---
website: $website
---
social_links: $social_links
---
social_card_image: $social_card_image
""")
    return tmpl.substitute(sponsor)


def json_to_dict(sponsor, _type, type_id):
    if _type.endswith("Sponsors"):
        what = _type.replace("Sponsors", "Sponsor")
    elif _type.endswith("Partners"):
        what = _type.replace("Partners", "Partner")
    else:
        what = f"{_type} Sponsor"
    s = {}
    s["type"] = what
    s["type_id"] = type_id
    s["id"] = sponsor.get("id")
    s["name"] = sponsor.get("name")
    s["logo"] = sponsor.get("logo")
    s["title"] = f"{sponsor.get('name')} - {what}"
    s["website"] = sponsor.get("website") or ""
    s["full_description"] = as_paragraphs(sponsor["description"])
    # One "Platform url" per line; the URL has no spaces, so the template
    # splits on the last one.
    s["social_links"] = "\n".join(
        f"{social_platform(url)} {url}" for url in sponsor.get("social", [])
    )
    # Point at the sponsor's own card only once it exists; with the field
    # empty, layout.html shares the edition's site card instead of a 404.
    card = f"/sponsors/{sponsor['id']}/social_card.png"
    has_card = (Path(__file__).parents[1] / f"content{card}").is_file()
    s["social_card_image"] = card if has_card else ""
    return s


def load_sponsors():
    sponsor_types = []
    sponsors = []
    with (Path(__file__).parents[1] / "databags/sponsors.yaml").open() as f:
        j = yaml.load(f, Loader=yaml.SafeLoader)
        sponsor_types = j["types"]
    validate_unique_ids(sponsor_types)
    validate_presentation(j)
    validate_social_links(sponsor_types)
    for sponsor_type in sponsor_types:
        sponsors += [
            json_to_dict(s, sponsor_type["name"], sponsor_type["id"])
            for s in sponsor_type["sponsors"]
        ]

    return sponsors


def save_as_lektor(sponsor):
    new_dir = Path(__file__).parents[1] / f"content/sponsors/{sponsor['id']}"
    new_dir.mkdir(parents=True, exist_ok=True)

    lektor = dict_to_lektor(sponsor)
    with (new_dir / "contents.lr").open("w") as f:
        f.write(lektor)


def main():
    sponsors = load_sponsors()
    print(sponsors)
    for sponsor in sponsors:
        save_as_lektor(sponsor)


if __name__ == "__main__":
    main()
