"""Tests for ``BranchAwareThreadPoolExecutor`` propagation."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from .context import BranchContext
from .executor import BranchAwareThreadPoolExecutor


def _capture_branch() -> str:
    return BranchContext.current()


def test_propagates_branch_to_worker():
    """The submitted callable runs in a thread, and the thread sees the
    submitter's active branch (not the default)."""
    with BranchAwareThreadPoolExecutor(max_workers=2) as ex:
        with BranchContext.use("feature-x"):
            fut = ex.submit(_capture_branch)
        assert fut.result(timeout=2) == "feature-x"


def test_branch_does_not_leak_to_subsequent_submissions():
    """A submission outside ``use(...)`` sees the default — the
    executor doesn't keep state across submissions."""
    with BranchAwareThreadPoolExecutor(max_workers=2) as ex:
        with BranchContext.use("feature-x"):
            inside = ex.submit(_capture_branch)
        outside = ex.submit(_capture_branch)
        assert inside.result(timeout=2) == "feature-x"
        assert outside.result(timeout=2) == "main"


def test_concurrent_submissions_have_independent_branches():
    """Two threads holding different branches should each see their own
    branch in the worker. This is the contract that makes per-request
    branch isolation safe under threaded fan-out."""
    seen: dict[str, str] = {}
    barrier = threading.Barrier(2)

    def submit_under(branch: str, key: str, ex: BranchAwareThreadPoolExecutor):
        with BranchContext.use(branch):
            fut = ex.submit(_capture_branch)
        # Synchronize so both submissions are in flight before either
        # result is read; rules out any "executor reused last context"
        # style bug.
        barrier.wait(timeout=2)
        seen[key] = fut.result(timeout=2)

    with BranchAwareThreadPoolExecutor(max_workers=4) as ex:
        threads = [
            threading.Thread(
                target=submit_under, args=("feature-a", "a", ex)
            ),
            threading.Thread(
                target=submit_under, args=("feature-b", "b", ex)
            ),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
    assert seen == {"a": "feature-a", "b": "feature-b"}


def test_map_propagates_branch():
    """``map`` is built on ``submit`` in the stdlib, so propagation
    inherits for free. Pin that behavior with a test."""
    with BranchAwareThreadPoolExecutor(max_workers=2) as ex:
        with BranchContext.use("feature-x"):
            results = list(ex.map(lambda _: BranchContext.current(), range(3)))
    assert results == ["feature-x"] * 3


def test_raw_thread_pool_does_not_propagate():
    """Sanity-check the documented motivation: a raw
    ``ThreadPoolExecutor`` is the broken default and the reason this
    wrapper exists."""
    with ThreadPoolExecutor(max_workers=1) as ex:
        with BranchContext.use("feature-x"):
            fut = ex.submit(_capture_branch)
        assert fut.result(timeout=2) == "main"  # NOT feature-x
