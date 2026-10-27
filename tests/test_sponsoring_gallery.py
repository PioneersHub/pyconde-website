"""The /sponsoring/ photo grid points only at photos that exist.

Lektor builds happily when a databag names a missing file or leaves out
alt text: the page ships with a broken image or an unlabelled one. These
checks catch both before the build does.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
GALLERY = yaml.safe_load((ROOT / "databags" / "sponsoring_gallery.yaml").read_text())
IMAGES = GALLERY["images"]


def test_image_dir_is_a_static_folder() -> None:
    image_dir = GALLERY["image_dir"]
    assert image_dir.startswith("/static/"), (
        f"image_dir must start with /static/, got {image_dir!r}"
    )
    assert (ROOT / "assets" / image_dir.lstrip("/")).is_dir()


@pytest.mark.parametrize("image", IMAGES, ids=[image["file"] for image in IMAGES])
def test_photo_file_exists(image: dict) -> None:
    path = ROOT / "assets" / GALLERY["image_dir"].lstrip("/") / image["file"]
    assert path.is_file(), f"{image['file']} is listed but missing from {path.parent}"


@pytest.mark.parametrize("image", IMAGES, ids=[image["file"] for image in IMAGES])
def test_photo_has_alt_text(image: dict) -> None:
    assert str(image.get("alt") or "").strip(), f"{image['file']} has no alt text"
