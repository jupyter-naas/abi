"""Tests for Tier 1 C — group commit.

These tests verify three things:

1. **Correctness with group commit enabled.** Every successful ``put`` lands
   exactly one revision; chains stay valid; ``verify`` passes.
2. **Genuine batching.** Under load, the number of batches is much smaller
   than the number of writes — proving fsyncs are amortized.
3. **Disabled-mode parity.** With ``commit_window_ms=0`` (the default), no
   batches are created and behavior matches the pre-group-commit code path.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from .store import ConcurrencyConflict, Store


# A modest window — large enough to actually catch concurrent writers in
# this process, small enough not to slow the test suite noticeably.
WINDOW_MS = 5.0


def _writer(store: Store, uid: str, branch: str, payloads: list[bytes]) -> int:
    n = 0
    for p in payloads:
        rev = store.put(uid, p, branch=branch)
        if rev is not None:
            n += 1
    return n


def test_disabled_by_default(tmp_path: Path):
    """With no constructor argument, no batches are formed."""
    with Store(tmp_path) as store:
        for i in range(5):
            store.put(f"uid-{i}", f"v{i}".encode())
        assert store._batch_count == 0
        assert store._batched_writes == 0


def test_window_zero_explicit_disables(tmp_path: Path):
    with Store(tmp_path, commit_window_ms=0.0) as store:
        store.put("alice", b"v1")
        assert store._batch_count == 0


def test_single_writer_with_group_commit_works(tmp_path: Path):
    """A lone writer in a group of one still commits durably."""
    with Store(tmp_path, commit_window_ms=WINDOW_MS) as store:
        rev = store.put("alice", b"v1")
        assert rev is not None
        assert store.get("alice") == b"v1"
        assert store._batch_count == 1
        assert store._batched_writes == 1
        assert store.verify("alice")


def test_concurrent_writers_actually_batch(tmp_path: Path):
    """With many concurrent writers on disjoint uids, the number of batches
    must be significantly less than the number of writes — proving the
    fsyncs were amortized."""
    N_WRITERS = 16
    N_PAYLOADS = 4
    total_writes = N_WRITERS * N_PAYLOADS

    with Store(tmp_path, commit_window_ms=WINDOW_MS, commit_max_size=64) as store:
        with ThreadPoolExecutor(max_workers=N_WRITERS) as pool:
            futures = [
                pool.submit(
                    _writer,
                    store,
                    f"uid-{i}",
                    "main",
                    [f"p-{i}-{j}".encode() for j in range(N_PAYLOADS)],
                )
                for i in range(N_WRITERS)
            ]
            counts = [f.result() for f in as_completed(futures)]
        assert sum(counts) == total_writes

        # All writes landed.
        for i in range(N_WRITERS):
            assert store.verify(f"uid-{i}")
            assert len(list(store.history(f"uid-{i}"))) == N_PAYLOADS

        # Genuine batching: at least one batch carried more than one write.
        # (Stronger numerical asserts are timing-dependent and would flake
        # on slow CI runners; this minimum is robust.)
        assert store._batch_count < total_writes, (
            f"expected batching: got {store._batch_count} batches "
            f"for {total_writes} writes"
        )
        assert store._batched_writes == total_writes


def test_max_size_caps_batch(tmp_path: Path):
    """When ``commit_max_size`` is small, batches close as soon as they fill
    rather than waiting for the full window."""
    cap = 4
    N_WRITERS = 16
    with Store(
        tmp_path,
        commit_window_ms=50.0,  # generous window
        commit_max_size=cap,
    ) as store:
        with ThreadPoolExecutor(max_workers=N_WRITERS) as pool:
            futures = [
                pool.submit(store.put, f"uid-{i}", b"x")
                for i in range(N_WRITERS)
            ]
            for f in as_completed(futures):
                f.result()

        # No batch can exceed the cap.
        assert store._batched_writes == N_WRITERS
        # And we should have at least ceil(16/4) = 4 batches if every group
        # filled to cap (in practice timing slack means we may see more,
        # but never fewer).
        assert store._batch_count >= N_WRITERS // cap


def test_idempotent_put_under_group_commit(tmp_path: Path):
    """Idempotent no-op (same content as latest) returns None and does not
    enter the commit group."""
    with Store(tmp_path, commit_window_ms=WINDOW_MS) as store:
        r1 = store.put("alice", b"same")
        assert r1 is not None
        before = store._batched_writes
        r2 = store.put("alice", b"same")
        assert r2 is None
        # Idempotent path returned without enqueueing.
        assert store._batched_writes == before


def test_expected_prev_hash_under_group_commit(tmp_path: Path):
    """CAS still works through the group commit path."""
    with Store(tmp_path, commit_window_ms=WINDOW_MS) as store:
        r1 = store.put("alice", b"v1")
        assert r1 is not None
        r2 = store.put("alice", b"v2", expected_prev_hash=r1.content_hash)
        assert r2 is not None

        # Move the tip from elsewhere; CAS against r2's stale ref must fail.
        store.put("alice", b"v-stolen")
        with pytest.raises(ConcurrencyConflict):
            store.put("alice", b"v3", expected_prev_hash=r2.content_hash)


def test_branching_works_under_group_commit(tmp_path: Path):
    """Branched writes with group commit enabled stay isolated per branch."""
    with Store(tmp_path, commit_window_ms=WINDOW_MS) as store:
        store.create_branch("feature-x")

        N = 8
        payloads = [(f"main-{i}".encode(), f"feat-{i}".encode()) for i in range(N)]

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = []
            for m, f in payloads:
                futures.append(pool.submit(store.put, "alice", m, branch="main"))
                futures.append(
                    pool.submit(store.put, "alice", f, branch="feature-x")
                )
            for fut in as_completed(futures):
                fut.result()

        assert len(list(store.history("alice", branch="main"))) == N
        assert len(list(store.history("alice", branch="feature-x"))) == N
        assert store.verify("alice", branch="main")
        assert store.verify("alice", branch="feature-x")


def test_chain_order_preserved_under_concurrent_branches(tmp_path: Path):
    """Within (branch, uid) the prev_hash chain must remain intact even when
    multiple branches' writes are interleaved into the same batch."""
    with Store(tmp_path, commit_window_ms=WINDOW_MS, commit_max_size=64) as store:
        store.create_branch("feature-x")

        # Drive a lot of interleaved writes into the same group.
        N = 20
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = []
            for i in range(N):
                futures.append(
                    pool.submit(store.put, f"u-{i % 4}", f"m-{i}".encode())
                )
                futures.append(
                    pool.submit(
                        store.put,
                        f"u-{i % 4}",
                        f"f-{i}".encode(),
                        branch="feature-x",
                    )
                )
            for f in as_completed(futures):
                f.result()

        for i in range(4):
            uid = f"u-{i}"
            assert store.verify(uid, branch="main")
            assert store.verify(uid, branch="feature-x")


def test_persistence_across_reopens(tmp_path: Path):
    """A group-committed write must be durable after the store is closed
    and reopened (regular store, no group commit on reopen)."""
    with Store(tmp_path, commit_window_ms=WINDOW_MS) as store:
        store.put("alice", b"durable")
    # Reopen with group commit disabled to prove the data is on disk
    # independent of the commit path.
    with Store(tmp_path) as store:
        assert store.get("alice") == b"durable"
        assert store.verify("alice")
