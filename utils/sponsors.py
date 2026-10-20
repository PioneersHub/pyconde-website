import sys
from collections import Counter
from pathlib import Path
from string import Template

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


def validate_presentation(data):
    """The sponsor wall template needs every tier's layout and every past lineup.

    Jinja renders a missing value as nothing, so a typo here would silently drop
    logos from the page; catch it before build instead.
    """
    errors = []
    for sponsor_type in data["types"]:
        is_partner = sponsor_type.get("partner") is True
        logo_size = sponsor_type.get("logo_size")
        if is_partner == (logo_size is not None):
            errors.append(
                f"type '{sponsor_type['id']}' needs exactly one of 'partner: true' or 'logo_size'"
            )
        elif logo_size is not None and logo_size not in LOGO_SIZES:
            errors.append(
                f"type '{sponsor_type['id']}' has logo_size '{logo_size}', expected one of {sorted(LOGO_SIZES)}"
            )

    past_editions = data.get("past_editions")
    if (
        not past_editions
        or not past_editions.get("title")
        or not past_editions.get("bags")
    ):
        errors.append("'past_editions' needs a 'title' and a non-empty 'bags' list")
    else:
        past_ids = set()
        for bag_name in past_editions["bags"]:
            bag_path = Path(__file__).parents[1] / f"databags/{bag_name}.yaml"
            if not bag_path.is_file():
                errors.append(
                    f"past_editions bag 'databags/{bag_name}.yaml' does not exist"
                )
                continue
            with bag_path.open() as f:
                past_data = yaml.load(f, Loader=yaml.SafeLoader)
            past_ids |= {
                s["id"] for t in past_data["types"] for s in t.get("sponsors", [])
            }
        for logo_id in past_editions.get("tonal_logos", []):
            if logo_id not in past_ids:
                errors.append(
                    f"past_editions tonal_logos id '{logo_id}' is not in any past lineup"
                )

    if errors:
        print("ERROR: Invalid sponsor wall configuration in databags/sponsors.yaml:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)


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
    s["full_description"] = sponsor.get("description")
    s["social_card_image"] = f"/sponsors/{sponsor['id']}/social_card.png"
    return s


def load_sponsors():
    sponsor_types = []
    sponsors = []
    with (Path(__file__).parents[1] / "databags/sponsors.yaml").open() as f:
        j = yaml.load(f, Loader=yaml.SafeLoader)
        sponsor_types = j["types"]
    validate_unique_ids(sponsor_types)
    validate_presentation(j)
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
