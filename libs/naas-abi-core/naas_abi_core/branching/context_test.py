"""Tests for ``BranchContext`` — default value, ``use(...)`` block,
nested contexts, exception unwinding, validation, async propagation."""

from __future__ import annotations

import asyncio

import pytest

from .context import BranchContext, DEFAULT_BRANCH
from .exceptions import BranchValidationError


def test_default_is_main():
    assert BranchContext.current() == DEFAULT_BRANCH
    assert DEFAULT_BRANCH == "main"
    assert BranchContext.is_default() is True


def test_use_sets_and_restores():
    assert BranchContext.current() == "main"
    with BranchContext.use("feature-x"):
        assert BranchContext.current() == "feature-x"
        assert BranchContext.is_default() is False
    assert BranchContext.current() == "main"


def test_use_yields_validated_name():
    with BranchContext.use("feature-x") as name:
        assert name == "feature-x"


def test_nested_use_stacks_correctly():
    with BranchContext.use("outer"):
        assert BranchContext.current() == "outer"
        with BranchContext.use("inner"):
            assert BranchContext.current() == "inner"
            with BranchContext.use("innermost"):
                assert BranchContext.current() == "innermost"
            assert BranchContext.current() == "inner"
        assert BranchContext.current() == "outer"
    assert BranchContext.current() == "main"


def test_use_restores_on_exception():
    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom):
        with BranchContext.use("feature-x"):
            assert BranchContext.current() == "feature-x"
            raise Boom("expected")
    assert BranchContext.current() == "main"


def test_validation_rejects_empty():
    with pytest.raises(BranchValidationError, match="non-empty"):
        with BranchContext.use(""):
            pass


def test_validation_rejects_non_string():
    with pytest.raises(BranchValidationError, match="must be a string"):
        with BranchContext.use(123):  # type: ignore[arg-type]
            pass


def test_validation_rejects_path_separators():
    for bad in ("a/b", "a\\b", "a\0b", ".", ".."):
        with pytest.raises(BranchValidationError):
            with BranchContext.use(bad):
                pass


def test_cannot_instantiate():
    with pytest.raises(TypeError):
        BranchContext()


# -------------------------------------------------------------------- async


def test_use_propagates_through_await():
    async def inner():
        # The await crosses a coroutine boundary — contextvars should
        # carry the active branch.
        await asyncio.sleep(0)
        return BranchContext.current()

    async def outer():
        with BranchContext.use("feature-x"):
            return await inner()

    assert asyncio.run(outer()) == "feature-x"


def test_use_propagates_to_create_task():
    """``asyncio.create_task`` copies the current context, so a task
    created inside ``use(...)`` sees the branch even after the creating
    coroutine yields."""

    async def task_body():
        await asyncio.sleep(0)
        return BranchContext.current()

    async def main():
        with BranchContext.use("feature-x"):
            t = asyncio.create_task(task_body())
        # Branch context already exited; the task still sees feature-x
        # because create_task captured the context at task creation.
        return await t

    assert asyncio.run(main()) == "feature-x"


def test_concurrent_async_tasks_have_independent_contexts():
    """Two coroutines running concurrently in the same event loop see
    their own ``use(...)`` value, not each other's. This is the
    contract that makes per-request branch isolation safe in async
    web frameworks."""

    seen: dict[str, str] = {}

    async def task(name: str, branch: str, barrier: asyncio.Event):
        with BranchContext.use(branch):
            await barrier.wait()
            seen[name] = BranchContext.current()

    async def main():
        barrier = asyncio.Event()
        coros = [task("a", "feature-a", barrier), task("b", "feature-b", barrier)]
        runners = [asyncio.create_task(c) for c in coros]
        # Let both tasks reach the barrier.
        await asyncio.sleep(0)
        barrier.set()
        await asyncio.gather(*runners)

    asyncio.run(main())
    assert seen == {"a": "feature-a", "b": "feature-b"}
