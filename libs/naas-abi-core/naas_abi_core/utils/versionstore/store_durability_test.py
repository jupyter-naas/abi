"""Tests for the durability mode wiring.

The behavioral guarantee of ``durability="full"`` (true on-disk persistence
on every platform, including Apple) is impossible to verify in-process
without inducing a real power loss. What we *can* verify is that the
machinery is wired correctly: the right SQLite PRAGMAs, the right code
path for fsync on Apple, and that both modes leave a working store.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from .store import (
    DURABILITY_FAST,
    DURABILITY_FULL,
    Store,
)


def _pragma(store: Store, name: str) -> object:
    return store._conn.execute(f"PRAGMA {name}").fetchone()[0]


def test_default_is_full(tmp_path: Path):
    with Store(tmp_path) as store:
        assert store._durability == DURABILITY_FULL


def test_invalid_durability_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        Store(tmp_path, durability="kinda")


def test_full_mode_sets_synchronous_full(tmp_path: Path):
    with Store(tmp_path, durability=DURABILITY_FULL) as store:
        # PRAGMA synchronous returns the int code: 2 == FULL.
        assert _pragma(store, "synchronous") == 2


def test_fast_mode_sets_synchronous_normal(tmp_path: Path):
    with Store(tmp_path, durability=DURABILITY_FAST) as store:
        # 1 == NORMAL.
        assert _pragma(store, "synchronous") == 1


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific PRAGMAs")
def test_full_mode_enables_fullfsync_on_darwin(tmp_path: Path):
    with Store(tmp_path, durability=DURABILITY_FULL) as store:
        assert _pragma(store, "fullfsync") == 1
        assert _pragma(store, "checkpoint_fullfsync") == 1
        assert store._use_full_fsync is True


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific PRAGMAs")
def test_fast_mode_disables_fullfsync_on_darwin(tmp_path: Path):
    with Store(tmp_path, durability=DURABILITY_FAST) as store:
        assert _pragma(store, "fullfsync") == 0
        assert store._use_full_fsync is False


@pytest.mark.skipif(sys.platform == "darwin", reason="non-Apple platforms")
def test_full_mode_no_fullfsync_off_apple(tmp_path: Path):
    """``"full"`` is identical to ``"fast"`` on non-Apple platforms because
    ``os.fsync`` already provides true durability there."""
    with Store(tmp_path, durability=DURABILITY_FULL) as store:
        assert store._use_full_fsync is False


def test_both_modes_produce_durable_writes_in_principle(tmp_path: Path):
    """Smoke test: writes land and are readable in both modes."""
    for mode in (DURABILITY_FULL, DURABILITY_FAST):
        sub = tmp_path / mode
        with Store(sub, durability=mode) as store:
            store.put("alice", b"hello")
        # Reopen — proves the data persisted across a close/open cycle.
        with Store(sub, durability=mode) as store:
            assert store.get("alice") == b"hello"
            assert store.verify("alice")


def test_group_commit_works_under_both_modes(tmp_path: Path):
    """The group commit code path picks up the durability mode through
    ``_sync_fd``; a quick smoke test under each."""
    for mode in (DURABILITY_FULL, DURABILITY_FAST):
        sub = tmp_path / mode
        with Store(sub, durability=mode, commit_window_ms=2.0) as store:
            store.put("alice", b"v1")
            store.put("alice", b"v2")
            assert store.get("alice") == b"v2"
            assert store.verify("alice")
