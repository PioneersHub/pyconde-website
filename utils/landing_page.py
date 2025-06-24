import json
from os import listdir

ASSET_FOLDERS = {
    "conference_images": "assets/static/landing-page/conference/",
    "content_images": "assets/static/landing-page/content/",
    "community_images": "assets/static/landing-page/community/",
}


def assets_to_json_file(assets: dict):
    with open("databags/landing_page.json", "w") as f:
        f.write(json.dumps(assets))


def files_to_relative_paths(relative_path: str) -> list[str]:
    return [relative_path.replace("assets", "") + p for p in listdir(relative_path)]


def main():
    assets = {}
    asset_types = ["conference_images", "content_images", "community_images"]
    for asset in asset_types:
        assets[asset] = files_to_relative_paths(ASSET_FOLDERS[asset])
    assets_to_json_file(assets)


if __name__ == "__main__":
    main()
