"""Tests for uuid7."""

from __future__ import annotations

import re

from .uuid7 import uuid7


UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def test_uuid7_format():
    for _ in range(100):
        u = uuid7()
        assert UUID_RE.match(u), f"bad uuid: {u}"


def test_uuid7_monotonic():
    ids = [uuid7() for _ in range(1000)]
    assert ids == sorted(ids), "uuid7s should be lexically monotonic within a process"


def test_uuid7_uniqueness():
    ids = {uuid7() for _ in range(10_000)}
    assert len(ids) == 10_000
