"""Tests for the minimal branching scaffold (read/write per branch, listing,
isolation between branches, rebuild_index across branches)."""

from __future__ import annotations

from pathlib import Path

import pytest

from .store import BranchNotFoundError, Store


def test_main_branch_seeded_by_default(tmp_path: Path):
    with Store(tmp_path) as store:
        assert "main" in store.list_branches()


def test_create_branch_lists_it(tmp_path: Path):
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        assert set(store.list_branches()) == {"main", "feature-x"}


def test_create_branch_rejects_bad_names(tmp_path: Path):
    with Store(tmp_path) as store:
        for bad in ["", ".", "..", "feat.x", "feat/x", "with\\back"]:
            with pytest.raises(ValueError):
                store.create_branch(bad)


def test_create_branch_rejects_unknown_parent(tmp_path: Path):
    with Store(tmp_path) as store:
        with pytest.raises(BranchNotFoundError):
            store.create_branch("feature-x", parent="ghost")


def test_writes_to_unknown_branch_raise(tmp_path: Path):
    with Store(tmp_path) as store:
        with pytest.raises(BranchNotFoundError):
            store.put("alice", b"v1", branch="ghost")


def test_branch_writes_are_isolated(tmp_path: Path):
    """A write on feature-x is invisible from main, and vice versa."""
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        store.put("alice", b"main-v1", branch="main")
        store.put("alice", b"feature-v1", branch="feature-x")

        assert store.get("alice", branch="main") == b"main-v1"
        assert store.get("alice", branch="feature-x") == b"feature-v1"
        # And history is per-branch:
        assert [r.content_hash for r in store.history("alice", branch="main")] != [
            r.content_hash for r in store.history("alice", branch="feature-x")
        ]


def test_main_branch_filename_unchanged(tmp_path: Path):
    """Backward-compat: main-branch revisions still use the 3-part filename."""
    with Store(tmp_path) as store:
        rev = store.put("alice", b"hello")
        assert rev is not None
        assert rev.filename.count(".") == 2  # ts.prev.content


def test_non_main_branch_filename_carries_branch(tmp_path: Path):
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        rev = store.put("alice", b"hi", branch="feature-x")
        assert rev is not None
        assert rev.filename.endswith(".feature-x")
        assert rev.filename.count(".") == 3  # ts.prev.content.branch


def test_idempotent_put_per_branch(tmp_path: Path):
    """Identical content on the same branch is a no-op; on a different
    branch it appends a fresh revision because the branch tip is empty."""
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        r1 = store.put("alice", b"same", branch="main")
        r1_dup = store.put("alice", b"same", branch="main")
        r2 = store.put("alice", b"same", branch="feature-x")
        assert r1 is not None
        assert r1_dup is None
        assert r2 is not None
        assert r2.branch == "feature-x"


def test_uids_at_scoped_to_branch(tmp_path: Path):
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        store.put("alice", b"a", branch="main")
        store.put("bob", b"b", branch="feature-x")

        assert {u for u, _ in store.uids_at(branch="main")} == {"alice"}
        assert {u for u, _ in store.uids_at(branch="feature-x")} == {"bob"}


def test_verify_per_branch(tmp_path: Path):
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        store.put("alice", b"v1", branch="main")
        store.put("alice", b"v2", branch="main")
        store.put("alice", b"x1", branch="feature-x")
        assert store.verify("alice", branch="main") is True
        assert store.verify("alice", branch="feature-x") is True


def test_rebuild_index_recovers_branches(tmp_path: Path):
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        store.put("alice", b"main-v1", branch="main")
        store.put("alice", b"feat-v1", branch="feature-x")
        store.put("alice", b"feat-v2", branch="feature-x")

        # Nuke the index entirely and rebuild from disk.
        store._conn.execute("DELETE FROM revisions")
        store._conn.execute("DELETE FROM branches WHERE name != 'main'")
        store.rebuild_index()

        assert set(store.list_branches()) >= {"main", "feature-x"}
        assert store.get("alice", branch="main") == b"main-v1"
        assert store.get("alice", branch="feature-x") == b"feat-v2"
        assert store.verify("alice", branch="main")
        assert store.verify("alice", branch="feature-x")
