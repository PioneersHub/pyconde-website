import json
import os
from string import Template


def dict_to_lektor(sponsor):
    tmpl = Template('''name: $name
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
''')
    return tmpl.substitute(sponsor)


def json_to_dict(sponsor, type, type_id):
    s = {}
    s["type"] = type
    s["type_id"] = type_id
    s["id"] = sponsor.get("id")
    s["name"] = sponsor.get("name")
    s["logo"] = sponsor.get("logo")
    s["title"] = sponsor.get("headline")
    s["website"] = sponsor.get("website") or ""
    s["full_description"] = sponsor.get("description")
    return s


def load_sponsors():
    sponsor_types = []
    sponsors = []
    with open("databags/sponsors.json") as f:
        j = json.load(f)
        sponsor_types = j["types"]
    for type in sponsor_types:
        sponsors += [json_to_dict(s, type["name"], type["id"])
                     for s in type["sponsors"]]

    return sponsors


def save_as_lektor(sponsor):
    new_dir = f"content/sponsors/{sponsor["id"]}"
    if not os.path.isdir(new_dir):
        os.mkdir(new_dir)

    lektor = dict_to_lektor(sponsor)
    with open(new_dir+"/contents.lr", "w") as f:
        f.write(lektor)


def main():
    sponsors = load_sponsors()
    print(sponsors)
    for sponsor in sponsors:
        save_as_lektor(sponsor)


if __name__ == "__main__":
    main()
