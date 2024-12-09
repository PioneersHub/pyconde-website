"""
For better readability, rearrange the FAQ databag in the order of the 'order' key within the section order
"""
import json
from pathlib import Path

db = Path(__file__).parents[1] / "databags/faq.json"
new_db = db.resolve()

data = json.load(db.open())


def current_model():
    sorted_data = {"sections": []}
    for section_dict in sorted(data["sections"], key=lambda x: x["order"]):
        qa = []
        for item in sorted(section_dict["qa"], key=lambda x: x["order"]):
            qa.append(item)
        section_dict["qa"] = qa
        sorted_data["sections"].append(section_dict)

    db.rename(db.with_suffix(".bak"))
    json.dump(sorted_data, new_db.open("w"), indent=4)


def first_model():
    """ Just for backup"""
    sorted_data = {"sections": [], "qa": []}
    for section_dict in sorted(data["sections"], key=lambda x: x["order"]):
        section_dict["qa"] = []
        for qa in sorted(data["qa"], key=lambda x: x["order"]):
            if qa["section"] == section_dict["id"]:
                section_dict["qa"].append(qa)
        sorted_data["sections"].append(section_dict)

    db.rename(db.with_suffix(".bak"))
    json.dump(sorted_data, new_db.open("w"), indent=4)


if __name__ == "__main__":
    current_model()
    # assert
a = 44