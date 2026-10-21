"""Reconciling /talks/{CODE}/ permalinks against a bucket.

A fake S3 client stands in for boto3: the reconcile runs its calls on a
thread pool, so a call-order-sensitive stub would test the scheduler, not
the outcome. What matters is the set of objects the bucket ends up with.
"""

from __future__ import annotations

import threading

import pytest
import talk_permalinks

BUCKET = "pyconde-test"


class FakeS3:
    """The four calls reconcile() makes, against an in-memory bucket.

    Parameter names are boto3's, hence the N803 exemptions. Every call
    asserts the bucket so a call aimed at the wrong one fails loudly.
    """

    def __init__(self, keys: list[str], page_size: int = 1000) -> None:
        self.objects: dict[str, str | None] = dict.fromkeys(keys)
        self.page_size = page_size
        self.fail_on: str | None = None
        self._lock = threading.Lock()

    def get_paginator(self, operation: str) -> FakeS3:
        assert operation == "list_objects_v2"
        return self

    def paginate(self, Bucket: str, Prefix: str):  # noqa: N803
        assert Bucket == BUCKET
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        for start in range(0, len(keys), self.page_size):
            yield {
                "Contents": [{"Key": k} for k in keys[start : start + self.page_size]]
            }
        if not keys:
            yield {"KeyCount": 0}  # S3 omits Contents for an empty listing

    def put_object(self, Bucket, Key, WebsiteRedirectLocation, Body) -> None:  # noqa: N803
        assert Bucket == BUCKET
        assert Body == b""
        if Key == self.fail_on:
            raise RuntimeError(f"AccessDenied on {Key}")
        with self._lock:
            self.objects[Key] = WebsiteRedirectLocation

    def delete_object(self, Bucket: str, Key: str) -> None:  # noqa: N803
        assert Bucket == BUCKET
        with self._lock:
            del self.objects[Key]


def test_writes_every_permalink_and_deletes_only_stale_ones() -> None:
    s3 = FakeS3(
        [
            "talks/AAAAAA/index.html",  # still wanted, gets repointed
            "talks/GONE01/index.html",  # withdrawn talk
            "talks/some-real-talk/index.html",  # a real page, never touched
            "talks/AAAAAA/social.png",  # not a permalink key
        ]
    )
    mapping = {"AAAAAA": "/archive/2026/talks/a/", "BBBBBB": "/talks/b/"}

    talk_permalinks.reconcile(s3, BUCKET, mapping)

    assert s3.objects == {
        "talks/AAAAAA/index.html": "/archive/2026/talks/a/",
        "talks/BBBBBB/index.html": "/talks/b/",
        "talks/some-real-talk/index.html": None,
        "talks/AAAAAA/social.png": None,
    }


def test_stale_permalinks_beyond_the_first_listing_page_are_deleted() -> None:
    stale = [f"talks/OLD{i:03d}/index.html" for i in range(5)]
    s3 = FakeS3(stale, page_size=2)

    talk_permalinks.reconcile(s3, BUCKET, {"NEW001": "/talks/n/"})

    assert s3.objects == {"talks/NEW001/index.html": "/talks/n/"}


def test_empty_bucket_gets_every_permalink() -> None:
    s3 = FakeS3([])

    talk_permalinks.reconcile(s3, BUCKET, {"AAAAAA": "/talks/a/"})

    assert s3.objects == {"talks/AAAAAA/index.html": "/talks/a/"}


def test_a_failed_write_fails_the_reconcile() -> None:
    s3 = FakeS3([])
    s3.fail_on = "talks/BBBBBB/index.html"

    with pytest.raises(RuntimeError, match="AccessDenied"):
        talk_permalinks.reconcile(s3, BUCKET, {"AAAAAA": "/a/", "BBBBBB": "/b/"})
