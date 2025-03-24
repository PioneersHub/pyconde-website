"""
Helper for automating the process of generating thank you banners.

- make sure to have @ in the data source header for image "@images" e.g., "@Logo"
- place all elements on master page.

"""

import csv
import json
from pathlib import Path

root = Path(__file__).parents[1]
databag = root / "databags/sponsors.json"

imgs = "/Users/hendorf/code/pioneershub/pyconde-website/assets/static/media/sponsors"

with databag.open("r") as f:
    sponsors = json.load(f)
output_csv = Path(__file__).parent / "sponsors.csv"

# Read JSON data
with databag.open("r", encoding="utf-8") as f:
    sponsors_data = json.load(f)

# Extract data into a structured format
rows = []
names = []
for sponsor_type in sponsors_data["types"]:
    type_name = sponsor_type["name"]
    type_id = sponsor_type["id"]
    for sponsor in sponsor_type.get("sponsors", []):
        logo = sponsor.get("logo", "").split("/")[-1]
        if logo:
            logo = f"{imgs}/{logo}"
        rows.append(
            {
                "Type Name": type_name,
                # "Type ID": type_id,
                "Sponsor Name": sponsor["name"],
                # "Sponsor ID": sponsor["id"],
                # "Headline": sponsor.get("headline", ""),
                # "Description": sponsor.get("description", ""),
                "@Logo": logo,
                # "Website": sponsor.get("website", ""),
                # "Scale": sponsor.get("scale", ""),
            }
        )
        names.append(sponsor["name"])


# Write to CSV
with output_csv.open("w", newline="", encoding="utf-8") as f:
    fieldnames = [
        "Type Name",
        # "Type ID",
        "Sponsor Name",
        # "Sponsor ID",
        # "Headline",
        # "Description",
        "@Logo",
        # "Website",
        # "Scale",
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
