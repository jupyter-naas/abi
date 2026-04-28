"""Tests for Store."""

from __future__ import annotations

import datetime as dt
import hashlib
import time
from pathlib import Path

import pytest

from .revision import HASH_LEN
from .store import GENESIS, Store


def test_put_and_get_latest(tmp_path: Path):
    with Store(tmp_path) as store:
        rev = store.put("alice", b"hello")
        assert rev is not None
        assert rev.prev_hash == GENESIS
        assert rev.content_hash == hashlib.sha256(b"hello").hexdigest()
        assert store.get("alice") == b"hello"


def test_missing_uid_returns_none(tmp_path: Path):
    with Store(tmp_path) as store:
        assert store.get("nobody") is None
        assert store.latest("nobody") is None


def test_idempotent_put_returns_none(tmp_path: Path):
    with Store(tmp_path) as store:
        r1 = store.put("alice", b"same")
        r2 = store.put("alice", b"same")
        assert r1 is not None
        assert r2 is None
        assert list(store.history("alice")) == [r1]


def test_prev_hash_chain(tmp_path: Path):
    with Store(tmp_path) as store:
        r1 = store.put("alice", b"v1")
        r2 = store.put("alice", b"v2")
        r3 = store.put("alice", b"v3")
        assert r1 is not None and r2 is not None and r3 is not None
        assert r1.prev_hash == GENESIS
        assert r2.prev_hash == r1.content_hash
        assert r3.prev_hash == r2.content_hash


def test_time_travel(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
        time.sleep(0.005)
        t_mid = dt.datetime.now(dt.timezone.utc)
        time.sleep(0.005)
        store.put("alice", b"v2")

        assert store.get("alice") == b"v2"
        assert store.get("alice", at=t_mid) == b"v1"


def test_time_travel_before_existence(tmp_path: Path):
    with Store(tmp_path) as store:
        t_before = dt.datetime.now(dt.timezone.utc)
        time.sleep(0.005)
        store.put("alice", b"v1")
        assert store.get("alice", at=t_before) is None


def test_empty_payload_is_valid_revision(tmp_path: Path):
    with Store(tmp_path) as store:
        rev = store.put("alice", b"")
        assert rev is not None
        assert store.get("alice") == b""
        # Empty payload is a legitimate revision, not a deletion signal.


def test_history_ordered(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
        store.put("alice", b"v2")
        store.put("alice", b"v3")
        ts = [r.ts_ns for r in store.history("alice")]
        assert ts == sorted(ts)


def test_uids_at(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"a1")
        store.put("bob", b"b1")
        store.put("alice", b"a2")
        latest = dict(store.uids_at())
        assert set(latest) == {"alice", "bob"}
        assert latest["alice"].content_hash == hashlib.sha256(b"a2").hexdigest()


def test_verify_passes(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
        store.put("alice", b"v2")
        store.put("alice", b"v3")
        assert store.verify("alice") is True


def test_verify_detects_content_tamper(tmp_path: Path):
    with Store(tmp_path) as store:
        rev = store.put("alice", b"v1")
        assert rev is not None
        # Tamper with the content while keeping the filename.
        rev.path.write_bytes(b"TAMPERED")
        assert store.verify("alice") is False


def test_rebuild_index_reconstructs_from_fs(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
        store.put("alice", b"v2")
        store.put("bob", b"b1")

        # Nuke the index.
        store._conn.execute("DELETE FROM revisions")
        assert list(store.uids()) == []

        store.rebuild_index()

        assert set(store.uids()) == {"alice", "bob"}
        assert store.get("alice") == b"v2"
        assert store.get("bob") == b"b1"
        assert store.verify("alice")
        assert store.verify("bob")


def test_rebuild_index_cleans_tmp_files(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
        # Simulate a crashed write leaving a .tmp file.
        uid_dir = store.data_dir / "alice"
        stale = uid_dir / "00000000000000000001.aaa.bbb.tmp"
        stale.write_bytes(b"garbage")
        assert stale.exists()

        store.rebuild_index()
        assert not stale.exists()


def test_filesystem_is_truth(tmp_path: Path):
    """Delete a revision file; rebuild should drop it from the index."""
    with Store(tmp_path) as store:
        r1 = store.put("alice", b"v1")
        r2 = store.put("alice", b"v2")
        assert r1 is not None and r2 is not None
        # Delete the second revision from the filesystem.
        r2.path.unlink()
        store.rebuild_index()
        # Only r1 should remain.
        history = list(store.history("alice"))
        assert len(history) == 1
        assert history[0].content_hash == r1.content_hash


def test_invalid_uid_rejected(tmp_path: Path):
    with Store(tmp_path) as store:
        with pytest.raises(ValueError):
            store.put("../escape", b"x")
        with pytest.raises(ValueError):
            store.put("", b"x")
        with pytest.raises(ValueError):
            store.put("with/slash", b"x")


def test_persists_across_instances(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
    with Store(tmp_path) as store:
        assert store.get("alice") == b"v1"


def test_revision_filename_matches_path(tmp_path: Path):
    with Store(tmp_path) as store:
        rev = store.put("alice", b"hello")
        assert rev is not None
        assert rev.path.exists()
        assert rev.path.name == rev.filename
        # Filename has expected shape: ts.prev.content (each hash HASH_LEN long).
        parts = rev.filename.split(".")
        assert len(parts) == 3
        assert len(parts[1]) == HASH_LEN
        assert len(parts[2]) == HASH_LEN
