"""Tests for the issue #876 branching surface: branch metadata sidecars,
fall-through reads, diff, delete_branch, merge (fast-forward and three-way)
with multi-parent ``.merge`` sidecars and the ``merges`` index table."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .revision import BRANCHES_DIRNAME, MERGE_SIDECAR_SUFFIX
from .store import (
    BranchDiff,
    BranchNotFoundError,
    MergeConflict,
    MergeStrategy,
    Store,
)


# ----------------------------------------------------------- branch sidecars


def test_main_branch_has_metadata_sidecar(tmp_path: Path):
    Store(tmp_path).close()
    sidecar = tmp_path / "data" / BRANCHES_DIRNAME / "main.json"
    assert sidecar.is_file()
    meta = json.loads(sidecar.read_text())
    assert meta["parent"] is None
    assert meta["fork_ts_ns"] == 0
    assert isinstance(meta["created_at"], int)


def test_create_branch_writes_sidecar(tmp_path: Path):
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
    sidecar = tmp_path / "data" / BRANCHES_DIRNAME / "feature-x.json"
    assert sidecar.is_file()
    meta = json.loads(sidecar.read_text())
    assert meta["parent"] == "main"
    assert meta["fork_ts_ns"] > 0
    assert isinstance(meta["created_at"], int)


def test_branch_name_merge_is_reserved(tmp_path: Path):
    with Store(tmp_path) as store:
        with pytest.raises(ValueError, match="Reserved branch name"):
            store.create_branch("merge")


def test_uid_branches_dir_name_is_reserved(tmp_path: Path):
    with Store(tmp_path) as store:
        with pytest.raises(ValueError, match="Reserved uid"):
            store.put(BRANCHES_DIRNAME, b"hi")


# -------------------------------------------------------- fall-through reads


def test_child_inherits_parent_state_at_fork(tmp_path: Path):
    """A fresh child branch sees its parent's tips at the moment of fork."""
    with Store(tmp_path) as store:
        store.put("alice", b"main-v1")
        store.put("bob", b"main-bob")
        store.create_branch("feature-x")
        # Without writes on feature-x, both uids resolve via fall-through.
        assert store.get("alice", branch="feature-x") == b"main-v1"
        assert store.get("bob", branch="feature-x") == b"main-bob"


def test_child_does_not_see_parent_writes_after_fork(tmp_path: Path):
    """Parent writes that happen after the fork are NOT visible on child."""
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
        store.create_branch("feature-x")
        store.put("alice", b"v2-on-main")  # post-fork on parent
        # feature-x still inherits v1; v2 is invisible.
        assert store.get("alice", branch="feature-x") == b"v1"
        assert store.get("alice", branch="main") == b"v2-on-main"


def test_child_overrides_inherited_uid(tmp_path: Path):
    """Own writes on child shadow the inherited tip."""
    with Store(tmp_path) as store:
        store.put("alice", b"main-v1")
        store.create_branch("feature-x")
        store.put("alice", b"feat-v1", branch="feature-x")
        assert store.get("alice", branch="feature-x") == b"feat-v1"
        assert store.get("alice", branch="main") == b"main-v1"


def test_uids_at_includes_inherited(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"a")
        store.put("bob", b"b")
        store.create_branch("feature-x")
        store.put("carol", b"c", branch="feature-x")
        visible = {u for u, _ in store.uids_at(branch="feature-x")}
        assert visible == {"alice", "bob", "carol"}


def test_fall_through_walks_grandparent(tmp_path: Path):
    """A branch of a branch falls all the way through to the root."""
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
        store.create_branch("feature-x")
        store.create_branch("feature-y", parent="feature-x")
        assert store.get("alice", branch="feature-y") == b"v1"


# ---------------------------------------------------------------- diff


def test_diff_empty_for_fresh_child(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
        store.create_branch("feature-x")
        diff = store.diff("feature-x", "main")
        assert isinstance(diff, BranchDiff)
        assert diff.is_empty()


def test_diff_detects_added_on_a(tmp_path: Path):
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        store.put("alice", b"new", branch="feature-x")
        diff = store.diff("feature-x", "main")
        assert "alice" in diff.added
        assert not diff.removed
        assert not diff.changed


def test_diff_detects_changed(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
        store.create_branch("feature-x")
        store.put("alice", b"feat", branch="feature-x")
        store.put("alice", b"main-v2")
        diff = store.diff("feature-x", "main")
        assert diff.changed == frozenset({"alice"})
        assert not diff.added
        assert not diff.removed


def test_diff_detects_removed(tmp_path: Path):
    """Symmetry: present on b, absent on a → 'removed' (with respect to a)."""
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        store.put("alice", b"main-only")
        # main has alice; feature-x has no own writes and forked before
        # alice was written, so feature-x's view doesn't include alice.
        diff = store.diff("feature-x", "main")
        assert diff.removed == frozenset({"alice"})


def test_diff_unknown_branch_raises(tmp_path: Path):
    with Store(tmp_path) as store:
        with pytest.raises(BranchNotFoundError):
            store.diff("ghost", "main")


# ----------------------------------------------------------- delete_branch


def test_delete_branch_removes_files_and_sidecars(tmp_path: Path):
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        store.put("alice", b"feat-v1", branch="feature-x")
        store.put("alice", b"feat-v2", branch="feature-x")
        # Sanity: files exist before delete.
        uid_dir = tmp_path / "data" / "alice"
        feat_files = [
            f for f in uid_dir.iterdir() if f.name.endswith(".feature-x")
        ]
        assert len(feat_files) == 2

        store.delete_branch("feature-x")
        # No more feature-x files anywhere.
        for f in uid_dir.iterdir():
            assert not f.name.endswith(".feature-x")
        # Branch sidecar gone.
        assert not (tmp_path / "data" / BRANCHES_DIRNAME / "feature-x.json").is_file()
        # Branch row gone.
        assert "feature-x" not in store.list_branches()


def test_delete_branch_refuses_main(tmp_path: Path):
    with Store(tmp_path) as store:
        with pytest.raises(ValueError, match="main"):
            store.delete_branch("main")


def test_delete_branch_refuses_with_children(tmp_path: Path):
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        store.create_branch("feature-y", parent="feature-x")
        with pytest.raises(ValueError, match="child"):
            store.delete_branch("feature-x")


def test_delete_branch_then_rebuild_index_no_orphans(tmp_path: Path):
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        store.put("alice", b"v1", branch="feature-x")
        store.delete_branch("feature-x")
        store.rebuild_index()
        assert "feature-x" not in store.list_branches()
        # Walking data dir, no feature-x revision files remain.
        for uid_dir in (tmp_path / "data").iterdir():
            if uid_dir.name == BRANCHES_DIRNAME:
                continue
            for f in uid_dir.iterdir():
                assert not f.name.endswith(".feature-x")


# ----------------------------------------------------- merge fast-forward


def test_merge_fast_forward_applies_source_tip(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"base")
        store.create_branch("feature-x")
        store.put("alice", b"feat", branch="feature-x")
        # Target hasn't moved → fast-forward.
        result = store.merge(
            "feature-x", "main", strategy=MergeStrategy.FAST_FORWARD
        )
        assert "alice" in result.fast_forwarded
        assert not result.conflicts
        assert store.get("alice", branch="main") == b"feat"


def test_merge_writes_merge_sidecar(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"base")
        store.create_branch("feature-x")
        store.put("alice", b"feat", branch="feature-x")
        store.merge("feature-x", "main")
        # The new revision on main is the merge revision; its sidecar
        # records the second parent (source tip's content_hash).
        uid_dir = tmp_path / "data" / "alice"
        sidecars = [
            f for f in uid_dir.iterdir() if f.name.endswith(MERGE_SIDECAR_SUFFIX)
        ]
        assert len(sidecars) == 1
        # The sidecar's payload should be a 64-char hex hash.
        content = sidecars[0].read_text().strip()
        assert len(content) == 64
        int(content, 16)  # parses as hex


def test_merge_no_op_when_target_already_has_source_content(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
        store.create_branch("feature-x")
        # Source unchanged from base.
        result = store.merge("feature-x", "main")
        assert result.no_op == {"alice"}
        assert not result.fast_forwarded
        assert not result.three_way_merged


def test_merge_idempotent_replay(tmp_path: Path):
    """Running the same merge twice is harmless: the second run finds the
    target already up to date and reports no_op."""
    with Store(tmp_path) as store:
        store.put("alice", b"base")
        store.create_branch("feature-x")
        store.put("alice", b"feat", branch="feature-x")
        store.merge("feature-x", "main")
        result = store.merge("feature-x", "main")
        assert result.no_op == {"alice"}
        assert not result.fast_forwarded


def test_merge_requires_direct_parent(tmp_path: Path):
    with Store(tmp_path) as store:
        store.create_branch("feature-x")
        store.create_branch("feature-y")  # sibling, not child of feature-x
        with pytest.raises(ValueError, match="source.parent == target"):
            store.merge("feature-y", "feature-x")


# ----------------------------------------------------- merge three-way


def test_merge_three_way_calls_resolver(tmp_path: Path):
    """Both sides moved from base → resolver runs and its bytes land on target."""
    with Store(tmp_path) as store:
        store.put("alice", b"base")
        store.create_branch("feature-x")
        store.put("alice", b"feat", branch="feature-x")
        store.put("alice", b"main-v2")  # target moves after fork

        calls: list[tuple[str, bytes | None, bytes, bytes]] = []

        def resolver(uid, base, src, tgt):
            calls.append((uid, base, src, tgt))
            return b"merged"

        result = store.merge("feature-x", "main", resolver=resolver)
        assert calls == [("alice", b"base", b"feat", b"main-v2")]
        assert result.three_way_merged == {"alice"}
        assert store.get("alice", branch="main") == b"merged"


def test_merge_three_way_resolver_none_is_conflict(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"base")
        store.create_branch("feature-x")
        store.put("alice", b"feat", branch="feature-x")
        store.put("alice", b"main-v2")

        with pytest.raises(MergeConflict) as exc_info:
            store.merge("feature-x", "main", resolver=lambda *a: None)
        assert "alice" in exc_info.value.conflicts
        # Target unchanged.
        assert store.get("alice", branch="main") == b"main-v2"


def test_merge_fast_forward_strategy_refuses_three_way(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"base")
        store.create_branch("feature-x")
        store.put("alice", b"feat", branch="feature-x")
        store.put("alice", b"main-v2")
        with pytest.raises(MergeConflict):
            store.merge(
                "feature-x", "main", strategy=MergeStrategy.FAST_FORWARD
            )


def test_merge_revision_passes_verify(tmp_path: Path):
    """Multi-parent revisions still satisfy the per-branch chain check."""
    with Store(tmp_path) as store:
        store.put("alice", b"base")
        store.create_branch("feature-x")
        store.put("alice", b"feat", branch="feature-x")
        store.merge("feature-x", "main")
        assert store.verify("alice", branch="main") is True
        assert store.verify("alice", branch="feature-x") is True


# ------------------------------------------------------- rebuild_index DAG


def test_rebuild_index_reconstructs_branch_dag_from_sidecars(tmp_path: Path):
    """Filesystem-only rebuild: nuke SQLite entirely, recover full DAG
    (parent + fork_ts_ns) from the on-disk sidecars."""
    with Store(tmp_path) as store:
        store.put("alice", b"v1")  # on main, before any branch exists
        store.create_branch("feature-x")
        store.create_branch("feature-y", parent="feature-x")
        store.put("alice", b"feat", branch="feature-x")
        original_meta_x = store._branch_meta("feature-x")
        original_meta_y = store._branch_meta("feature-y")
        assert original_meta_x is not None and original_meta_y is not None

        # Nuke the entire index (mimicking total SQLite loss).
        store._conn.execute("DELETE FROM revisions")
        store._conn.execute("DELETE FROM merges")
        store._conn.execute("DELETE FROM branches")
        store.rebuild_index()

        # DAG fully reconstructed.
        assert set(store.list_branches()) >= {"main", "feature-x", "feature-y"}
        rebuilt_x = store._branch_meta("feature-x")
        rebuilt_y = store._branch_meta("feature-y")
        assert rebuilt_x == original_meta_x
        assert rebuilt_y == original_meta_y
        # Reads still work, fall-through and all.
        assert store.get("alice", branch="feature-y") == b"v1"


def test_rebuild_index_reconstructs_merges_table(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"base")
        store.create_branch("feature-x")
        store.put("alice", b"feat", branch="feature-x")
        store.merge("feature-x", "main")

        with store._db_lock:
            before = store._conn.execute(
                "SELECT branch, uid, ts_ns, other_parent FROM merges"
            ).fetchall()
        assert len(before) == 1

        store._conn.execute("DELETE FROM merges")
        store.rebuild_index()

        with store._db_lock:
            after = store._conn.execute(
                "SELECT branch, uid, ts_ns, other_parent FROM merges"
            ).fetchall()
        assert before == after


def test_rebuild_index_drops_orphan_merge_sidecars(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
        # Create a stray .merge sidecar that doesn't pair with anything real.
        uid_dir = tmp_path / "data" / "alice"
        orphan = uid_dir / ("00000000000000000000."
                            + "0" * 64 + "."
                            + "1" * 64
                            + MERGE_SIDECAR_SUFFIX)
        orphan.write_text("a" * 64)
        store.rebuild_index()
        assert not orphan.exists()
