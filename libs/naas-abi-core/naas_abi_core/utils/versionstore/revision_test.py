"""Tests for Revision."""

from __future__ import annotations

from pathlib import Path

import pytest

from .revision import HASH_LEN, Revision


H1 = "a" * HASH_LEN
H2 = "b" * HASH_LEN


def test_filename_round_trip(tmp_path: Path):
    rev = Revision(uid="u", ts_ns=123, prev_hash=H1, content_hash=H2, path=tmp_path)
    parsed = Revision.parse_filename("u", rev.filename, tmp_path)
    assert parsed.uid == "u"
    assert parsed.ts_ns == 123
    assert parsed.prev_hash == H1
    assert parsed.content_hash == H2


def test_filename_zero_pads_timestamp(tmp_path: Path):
    rev = Revision(uid="u", ts_ns=1, prev_hash=H1, content_hash=H2, path=tmp_path)
    assert rev.filename.startswith("0" * 19 + "1.")


def test_parse_rejects_bad_parts(tmp_path: Path):
    with pytest.raises(ValueError):
        Revision.parse_filename("u", "nope", tmp_path)
    with pytest.raises(ValueError):
        Revision.parse_filename("u", f"123.{H1}.short", tmp_path)
    with pytest.raises(ValueError):
        Revision.parse_filename("u", f"notadigit.{H1}.{H2}", tmp_path)


def test_timestamp_is_utc(tmp_path: Path):
    rev = Revision(
        uid="u",
        ts_ns=1_700_000_000_000_000_000,
        prev_hash=H1,
        content_hash=H2,
        path=tmp_path,
    )
    assert rev.timestamp.tzinfo is not None
