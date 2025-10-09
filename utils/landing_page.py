from pathlib import Path
from random import shuffle

import yaml

ASSET_FOLDERS = {
    "venue_images": "assets/static/landing-page/venue/",
    "community_images": "assets/static/landing-page/community/",
    "speaker_images": "assets/static/landing-page/speakers/",
    "promo_images": "assets/static/landing-page/promo_images/",
    "organizer_images": "assets/static/landing-page/organizers/",
    "workshop_images": "assets/static/landing-page/workshops/",
}


def assets_to_json_file(assets: dict):
    with open("databags/landing_page.yaml", "w") as f:
        yaml.dump(assets, f)


def files_to_relative_paths(relative_path: str) -> list[str]:
    images = [
        str(x)
        for x in Path(relative_path).glob("*")
        # ignore non-suitable files
        if x.suffix in [".jpg", ".png", ".jpeg"]
    ]
    return [p.replace("assets", "") for p in images]


def main():
    assets = {}
    for asset, _ in ASSET_FOLDERS.items():
        the_assets = files_to_relative_paths(ASSET_FOLDERS[asset])
        shuffle(the_assets)
        assets[asset] = the_assets
    assets_to_json_file(assets)


if __name__ == "__main__":
    main()
