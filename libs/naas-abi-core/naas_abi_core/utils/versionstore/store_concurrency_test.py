"""Tests for Tier 1 A & B concurrency: per-uid and per-(branch, uid) writes.

These tests exercise the lock-free retry path. Multiple writer threads target
the store simultaneously; we assert that:

  * No writes are lost (every successful put yields a revision in the chain).
  * The Merkle chain stays valid on every (uid, branch).
  * Concurrent writers to *different* uids or *different* branches succeed
    without escalating to ``ConcurrencyConflict``.
  * Concurrent writers to the *same* (uid, branch) without an
    ``expected_prev_hash`` retry transparently and all eventually land.
  * ``expected_prev_hash`` mismatches raise ``ConcurrencyConflict``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from .store import ConcurrencyConflict, Store


# Each test creates its own Store. SQLite with check_same_thread=False is fine
# for our usage because every method takes the connection's internal mutex
# briefly — we never hold a transaction across threads.


def _writer(store: Store, uid: str, branch: str, payloads: list[bytes]) -> int:
    """Append every payload in order under (uid, branch); return count of writes."""
    n = 0
    for p in payloads:
        rev = store.put(uid, p, branch=branch)
        if rev is not None:
            n += 1
    return n


# ------------------------------------------------------------------ Tier 1 A


def test_concurrent_writes_to_different_uids_all_succeed(tmp_path: Path):
    """Tier 1 A: writers on disjoint uids never conflict."""
    with Store(tmp_path) as store:
        N_WRITERS = 8
        N_PAYLOADS = 20
        with ThreadPoolExecutor(max_workers=N_WRITERS) as pool:
            futures = [
                pool.submit(
                    _writer,
                    store,
                    f"uid-{i}",
                    "main",
                    [f"payload-{i}-{j}".encode() for j in range(N_PAYLOADS)],
                )
                for i in range(N_WRITERS)
            ]
            counts = [f.result() for f in as_completed(futures)]

        assert sum(counts) == N_WRITERS * N_PAYLOADS
        for i in range(N_WRITERS):
            uid = f"uid-{i}"
            assert store.verify(uid)
            assert (
                len(list(store.history(uid))) == N_PAYLOADS
            ), f"missing revisions for {uid}"


def test_concurrent_writes_to_same_uid_all_land(tmp_path: Path):
    """Tier 1 A retry path: writers fighting for the same (uid, branch) all
    succeed eventually. The chain stays valid; the count matches; no payload
    is lost."""
    with Store(tmp_path) as store:
        N_WRITERS = 8
        N_PAYLOADS = 10  # per writer
        with ThreadPoolExecutor(max_workers=N_WRITERS) as pool:
            futures = [
                pool.submit(
                    _writer,
                    store,
                    "shared",
                    "main",
                    [f"writer-{w}-payload-{j}".encode() for j in range(N_PAYLOADS)],
                )
                for w in range(N_WRITERS)
            ]
            counts = [f.result() for f in as_completed(futures)]

        assert sum(counts) == N_WRITERS * N_PAYLOADS
        history = list(store.history("shared"))
        assert len(history) == N_WRITERS * N_PAYLOADS
        assert store.verify("shared") is True


# ------------------------------------------------------------------ Tier 1 B


def test_concurrent_writes_to_same_uid_different_branches(tmp_path: Path):
    """Tier 1 B: per-(branch, uid) concurrency. Two writers on different
    branches touching the same uid succeed in parallel without conflict, and
    the chains on each branch are independent."""
    with Store(tmp_path) as store:
        store.create_branch("feature-x")

        N_WRITERS_PER_BRANCH = 4
        N_PAYLOADS = 25

        with ThreadPoolExecutor(max_workers=2 * N_WRITERS_PER_BRANCH) as pool:
            futures = []
            for w in range(N_WRITERS_PER_BRANCH):
                for branch in ("main", "feature-x"):
                    futures.append(
                        pool.submit(
                            _writer,
                            store,
                            "shared",
                            branch,
                            [f"{branch}-{w}-{j}".encode() for j in range(N_PAYLOADS)],
                        )
                    )
            counts = [f.result() for f in as_completed(futures)]

        assert sum(counts) == 2 * N_WRITERS_PER_BRANCH * N_PAYLOADS

        for branch in ("main", "feature-x"):
            history = list(store.history("shared", branch=branch))
            assert (
                len(history) == N_WRITERS_PER_BRANCH * N_PAYLOADS
            ), f"branch {branch}: bad count"
            assert store.verify("shared", branch=branch) is True


# ----------------------------------------------------- expected_prev_hash CAS


def test_expected_prev_hash_matches(tmp_path: Path):
    with Store(tmp_path) as store:
        r1 = store.put("alice", b"v1")
        assert r1 is not None
        # CAS against the known tip succeeds.
        r2 = store.put("alice", b"v2", expected_prev_hash=r1.content_hash)
        assert r2 is not None
        assert r2.prev_hash == r1.content_hash


def test_expected_prev_hash_mismatch_raises(tmp_path: Path):
    with Store(tmp_path) as store:
        store.put("alice", b"v1")
        store.put("alice", b"v2")  # tip moved
        # CAS against the stale tip — must fail loudly, not silently retry.
        with pytest.raises(ConcurrencyConflict):
            store.put("alice", b"v3", expected_prev_hash="0" * 64)


def test_expected_prev_hash_on_first_revision(tmp_path: Path):
    """For a fresh (uid, branch), the expected_prev_hash must be GENESIS."""
    from .store import GENESIS

    with Store(tmp_path) as store:
        r = store.put("alice", b"v1", expected_prev_hash=GENESIS)
        assert r is not None
        assert r.prev_hash == GENESIS


def test_expected_prev_hash_under_concurrent_writer(tmp_path: Path):
    """If a parallel writer moves the tip, our CAS write must raise."""
    with Store(tmp_path) as store:
        r1 = store.put("alice", b"v1")
        assert r1 is not None

        # Pre-move the tip from another caller's perspective.
        store.put("alice", b"v-stolen")

        # Now r1 is stale. CAS against it should raise.
        with pytest.raises(ConcurrencyConflict):
            store.put("alice", b"v-mine", expected_prev_hash=r1.content_hash)


# Note: the retry loop's *bound* is implicitly exercised by the contention
# tests above — N writers against one (uid, branch) all complete only because
# losers retry transparently. A deterministic test of "exhausted max_retries
# raises ConcurrencyConflict" would require monkey-patching the SELECT path,
# which is more invasive than it's worth here.
