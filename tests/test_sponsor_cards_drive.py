"""Sponsor cards for Google Drive: file names, and reruns that replace.

Run with: uv run --extra cards --extra drive pytest tests/test_sponsor_cards_drive.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip(
    "uharfbuzz", reason="the social-card engine needs: uv run --extra cards pytest"
)
pytest.importorskip(
    "googleapiclient", reason="the Drive upload needs: uv run --extra drive pytest"
)

import page_social_cards as pc  # noqa: E402
import sponsor_cards_drive as scd  # noqa: E402

FIELD = re.compile(r"(\w+) = '((?:[^'\\]|\\.)*)'")


class FakeDrive:
    """Just enough of the Drive v3 files() API: items with a name, a type
    and one parent, found by the queries sponsor_cards_drive sends."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}
        self.updates: list[str] = []

    def files(self) -> FakeDrive:
        return self

    def execute(self):
        return self._result

    def list(self, q: str, **_) -> FakeDrive:
        parent = re.match(r"'([^']*)' in parents", q).group(1)
        wanted = dict(FIELD.findall(q))
        self._result = {
            "files": [
                {"id": item_id}
                for item_id, item in self.items.items()
                if item["parent"] == parent
                and item["name"] == wanted["name"]
                and item["mimeType"] == wanted["mimeType"]
            ]
        }
        return self

    def create(self, body: dict, media_body=None, **_) -> FakeDrive:
        item_id = f"id{len(self.items)}"
        mime = body.get("mimeType") or media_body.mimetype()
        self.items[item_id] = {
            "name": body["name"],
            "mimeType": mime,
            "parent": body["parents"][0],
        }
        self._result = {"id": item_id}
        return self

    def update(self, fileId: str, **_) -> FakeDrive:  # noqa: N803 (Drive's name)
        self.updates.append(fileId)
        self._result = {}
        return self


@pytest.fixture
def lidl_cards(tmp_path, monkeypatch) -> list[Path]:
    monkeypatch.setattr(scd, "OUT_DIR", tmp_path)
    config = pc.load_config()
    return scd.card_files(pc.CONTENT_DIR / "sponsors" / "lidl", "sponsor", config)


def test_every_format_is_named_after_the_sponsor(lidl_cards):
    names = [p.name for p in lidl_cards]
    assert names == [
        "lidl_og.png",
        "lidl_square.png",
        "lidl_portrait.png",
        "lidl_story.png",
    ]
    assert {p.parent.name for p in lidl_cards} == {"lidl"}
    with Image.open(lidl_cards[-1]) as story:
        assert story.size == (1080, 1920)


def test_upload_makes_one_folder_per_sponsor(lidl_cards):
    drive = FakeDrive()
    scd.upload(drive, "root", {"lidl": lidl_cards})
    folders = [i for i in drive.items.values() if i["mimeType"] == scd.FOLDER_TYPE]
    assert [(f["name"], f["parent"]) for f in folders] == [("lidl", "root")]
    pngs = sorted(
        i["name"] for i in drive.items.values() if i["mimeType"] == scd.PNG_TYPE
    )
    assert pngs == sorted(p.name for p in lidl_cards)


def test_a_rerun_replaces_instead_of_duplicating(lidl_cards):
    drive = FakeDrive()
    scd.upload(drive, "root", {"lidl": lidl_cards})
    before = dict(drive.items)
    scd.upload(drive, "root", {"lidl": lidl_cards})
    assert drive.items == before
    assert len(drive.updates) == len(lidl_cards)


def test_a_sponsor_without_a_usable_logo_is_reported_not_uploaded(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(scd, "OUT_DIR", tmp_path)
    config = pc.load_config()
    slug, outcome = scd._draw(
        (pc.CONTENT_DIR / "sponsors" / "academis", "sponsor", config)
    )
    assert slug == "academis"
    assert "outlined text" in outcome
    assert not (tmp_path / "academis").exists()
