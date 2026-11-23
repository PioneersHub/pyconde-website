"""Draw every sponsor's thank-you card in every format and put it in Drive.

The site only needs the og card; sponsors and the social-media team also
want the square, portrait and story versions. This draws all of them with
the same engine as `make page-cards` and uploads them into the Drive folder
named under `drive_upload` in utils/social_cards/pages.yaml, one subfolder
per sponsor:

    <slug>/<slug>_og.png, <slug>_square.png, <slug>_portrait.png, <slug>_story.png

where <slug> is the sponsor's folder under content/sponsors. A rerun
replaces files of the same name, so Drive never holds two versions of a
card. A sponsor whose card cannot be drawn in every format (an unusable
logo, a title the fonts cannot set) is reported and left out entirely; the
others are still uploaded, and the run exits non-zero.

This is a local process, run by hand; neither the site build nor CI runs
it. It signs in to Drive exactly as utils/drive_fetch.py does, with the same
OAuth client and token (`drive_token_json` in the pytanis config).

Usage:
    make sponsor-cards-upload
"""

import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import page_social_cards as pc
from drive_fetch import drive_service, fail
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from social_cards.brand import REPO_ROOT, load_brand
from social_cards.content import CardContentError
from social_cards.pipeline import NoValidDesignError, design, export

OUT_DIR = REPO_ROOT / "build" / "sponsor-cards"
FOLDER_TYPE = "application/vnd.google-apps.folder"
PNG_TYPE = "image/png"


def card_files(page_dir: Path, model: str, config: dict[str, Any]) -> list[Path]:
    """Draw one page's card in every format into OUT_DIR/<slug>/; the
    files, or PageCardError naming the first format that failed."""
    brand = load_brand()
    slug = page_dir.name
    card = pc.card_for(page_dir, model, pc.CONTENT_DIR, config, brand)
    files = []
    for fmt in brand.raw["formats"]:
        try:
            result = design(card, fmt, brand)
        except NoValidDesignError as err:
            raise pc.PageCardError(str(err).splitlines()[0]) from None
        files.append(export(result, brand, OUT_DIR / slug / f"{slug}_{fmt}.png"))
    return files


def _draw(page: tuple[Path, str, dict[str, Any]]) -> tuple[str, list[Path] | str]:
    """Worker: a page's files, or why it got none."""
    page_dir, model, config = page
    try:
        return page_dir.name, card_files(page_dir, model, config)
    except (pc.PageCardError, CardContentError) as err:
        return page_dir.name, str(err).splitlines()[0]


def draw_all(config: dict[str, Any]) -> tuple[dict[str, list[Path]], dict[str, str]]:
    """Every page of the upload model, drawn; ({slug: files}, {slug: why not})."""
    model = config["drive_upload"]["model"]
    pages = [
        (page_dir, m, config)
        for page_dir, m in pc.pages(pc.CONTENT_DIR, config, preview=True)
        if m == model
    ]
    if not pages:
        fail(f"no pages of model {model!r} found under {pc.CONTENT_DIR}")
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    drawn, failed = {}, {}
    with ProcessPoolExecutor() as pool:
        for slug, outcome in pool.map(_draw, pages):
            if isinstance(outcome, str):
                failed[slug] = outcome
            else:
                drawn[slug] = outcome
    return drawn, failed


def _quoted(name: str) -> str:
    return "'" + name.replace("\\", "\\\\").replace("'", "\\'") + "'"


def find_child(drive, parent: str, name: str, mime_type: str) -> str | None:
    """The id of the one item called `name` in `parent`, or None."""
    query = (
        f"{_quoted(parent)} in parents and name = {_quoted(name)} "
        f"and mimeType = {_quoted(mime_type)} and trashed = false"
    )
    found = (
        drive.files()
        .list(
            q=query,
            fields="files(id)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()["files"]
    )
    if len(found) > 1:
        fail(f"Drive folder {parent} holds {len(found)} items called {name}; keep one")
    return found[0]["id"] if found else None


def ensure_folder(drive, parent: str, name: str) -> str:
    """The id of subfolder `name` of `parent`, created when missing."""
    if folder := find_child(drive, parent, name, FOLDER_TYPE):
        return folder
    body = {"name": name, "mimeType": FOLDER_TYPE, "parents": [parent]}
    return (
        drive.files()
        .create(body=body, fields="id", supportsAllDrives=True)
        .execute()["id"]
    )


def put_png(drive, folder: str, path: Path) -> str:
    """Upload `path` into `folder`, replacing a file of the same name."""
    media = MediaFileUpload(path, mimetype=PNG_TYPE)
    if existing := find_child(drive, folder, path.name, PNG_TYPE):
        drive.files().update(
            fileId=existing, media_body=media, supportsAllDrives=True
        ).execute()
        return "replaced"
    body = {"name": path.name, "parents": [folder]}
    drive.files().create(
        body=body, media_body=media, fields="id", supportsAllDrives=True
    ).execute()
    return "uploaded"


def upload(drive, root: str, drawn: dict[str, list[Path]]) -> None:
    for slug, files in sorted(drawn.items()):
        folder = ensure_folder(drive, root, slug)
        done = [f"{path.name} {put_png(drive, folder, path)}" for path in files]
        print(f"{slug}: {', '.join(done)}")


def main() -> int:
    config = pc.load_config()
    # Authorise before drawing, so a missing token fails in seconds.
    drive = drive_service()
    drawn, failed = draw_all(config)
    print(f"Drew {sum(map(len, drawn.values()))} cards into {OUT_DIR}")
    try:
        upload(drive, config["drive_upload"]["folder"], drawn)
    except HttpError as error:
        fail(f"Google Drive API {error.status_code}: {error.reason}")
    for slug, why in sorted(failed.items()):
        print(f"{slug}: not uploaded, {why}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
