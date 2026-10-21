"""Skipping files the bucket already holds.

`aws s3 sync` uploads when sizes differ or the local file is newer. These
tests pin the half that deploy_to_s3 controls: which files get backdated
(skipped) and which keep a fresh mtime (uploaded). A wrong skip would leave
stale content live, so every case that is not a provable match must upload.
"""

from __future__ import annotations

import hashlib
import time

import deploy_to_s3
import pytest


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setattr(deploy_to_s3, "SITE_DIR", tmp_path)
    return tmp_path


def write(site, key: str, content: bytes):
    path = site / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def fingerprint(content: bytes) -> tuple[int, str]:
    return len(content), hashlib.md5(content).hexdigest()


def is_skipped(path) -> bool:
    return path.stat().st_mtime == deploy_to_s3.UNCHANGED_MTIME


def test_single_part_etag_is_the_md5(site) -> None:
    path = write(site, "a.html", b"<p>hello</p>")
    assert deploy_to_s3.s3_etag(path) == hashlib.md5(b"<p>hello</p>").hexdigest()


def test_empty_file_etag(site) -> None:
    path = write(site, "empty.txt", b"")
    assert deploy_to_s3.s3_etag(path) == hashlib.md5(b"").hexdigest()


def test_multipart_etag_matches_s3s_scheme(site, monkeypatch) -> None:
    monkeypatch.setattr(deploy_to_s3, "MULTIPART_THRESHOLD", 4)
    monkeypatch.setattr(deploy_to_s3, "MULTIPART_CHUNKSIZE", 4)
    path = write(site, "big.pdf", b"aaaabbbbcc")
    parts = b"".join(hashlib.md5(p).digest() for p in (b"aaaa", b"bbbb", b"cc"))
    assert deploy_to_s3.s3_etag(path) == f"{hashlib.md5(parts).hexdigest()}-3"


def test_build_state_is_never_fingerprinted(site) -> None:
    write(site, ".lektor/buildstate", b"db")
    write(site, "index.html", b"home")
    assert set(deploy_to_s3.local_fingerprints()) == {"index.html"}


def test_only_identical_content_is_skipped(site) -> None:
    same = write(site, "static/logo.svg", b"<svg/>")
    edited = write(site, "index.html", b"new text")  # same size as the object
    new = write(site, "blog/post/index.html", b"fresh")
    remote = {
        "static/logo.svg": fingerprint(b"<svg/>"),
        "index.html": fingerprint(b"old text"),
    }

    unchanged = deploy_to_s3.mark_unchanged(deploy_to_s3.local_fingerprints(), remote)

    assert unchanged == 1
    assert is_skipped(same)
    assert not is_skipped(edited)
    assert not is_skipped(new)


def test_a_skip_for_one_bucket_does_not_carry_over_to_the_next(site) -> None:
    path = write(site, "index.html", b"home")
    local = deploy_to_s3.local_fingerprints()

    deploy_to_s3.mark_unchanged(local, {"index.html": fingerprint(b"home")})
    assert is_skipped(path)

    before = time.time()
    deploy_to_s3.mark_unchanged(local, {})
    assert path.stat().st_mtime >= before - 1


def test_remote_listing_spans_pages_and_strips_etag_quotes() -> None:
    class FakeS3:
        def get_paginator(self, operation):
            assert operation == "list_objects_v2"
            return self

        def paginate(self, Bucket):  # noqa: N803 — boto3's name
            assert Bucket == "b"
            yield {"Contents": [{"Key": "a", "Size": 1, "ETag": '"x"'}]}
            yield {"Contents": [{"Key": "b", "Size": 2, "ETag": '"y-2"'}]}

    assert deploy_to_s3.remote_fingerprints(FakeS3(), "b") == {
        "a": (1, "x"),
        "b": (2, "y-2"),
    }
