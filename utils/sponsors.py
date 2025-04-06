import json
from pathlib import Path
from string import Template


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
    s = {}
    s["type"] = _type
    s["type_id"] = type_id
    s["id"] = sponsor.get("id")
    s["name"] = sponsor.get("name")
    s["logo"] = sponsor.get("logo")
    s["title"] = f"{sponsor.get('name')}-{_type} of PyCon DE & PyData"
    s["website"] = sponsor.get("website") or ""
    s["full_description"] = sponsor.get("description")
    s["social_card_image"] = f"/sponsors/{sponsor['id']}/social_card.png"
    return s


def load_sponsors():
    sponsor_types = []
    sponsors = []
    with (Path(__file__).parents[1] / "databags/sponsors.json").open() as f:
        j = json.load(f)
        sponsor_types = j["types"]
    for type in sponsor_types:
        sponsors += [
            json_to_dict(s, type["name"], type["id"]) for s in type["sponsors"]
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
