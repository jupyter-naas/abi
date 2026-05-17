"""``BranchContext``: ambient "active branch" propagation primitive.

The branching architecture from spec #865 has every Tier-1 service
consult an *active branch* on every read and write. Threading that
branch through every service method would be a signature explosion;
instead we put it in a ``contextvars.ContextVar`` so any code under a
``BranchContext.use(...)`` block sees the same value, including across
``await``, ``asyncio.create_task``, and ``copy_context().run(...)``
boundaries (this is the standard contextvars contract).

The default is ``"main"``. Code that has not opted in sees no behavior
change.

Usage
-----

::

    from naas_abi_core.branching import BranchContext

    BranchContext.current()  # → "main"

    with BranchContext.use("feature-x"):
        BranchContext.current()  # → "feature-x"
        # …every adapter underneath sees feature-x…

    BranchContext.current()  # → "main" again

Async
-----

``contextvars`` already propagates correctly through ``asyncio``: a
``ContextVar`` set in a parent task is visible inside ``await``-ed
coroutines and inside ``asyncio.create_task(...)`` (which copies the
current context by default). No wrapper is needed for async.

Threads
-------

Standard ``ThreadPoolExecutor`` does **not** propagate context to
worker threads. Use ``BranchAwareThreadPoolExecutor`` from
``naas_abi_core.branching.executor`` instead — it calls
``copy_context().run(fn)`` on every submission so the worker sees the
submitter's active branch. The repository test suite includes a guard
that fails CI if a raw ``ThreadPoolExecutor`` is imported anywhere
under ``naas_abi_core/`` (see ``no_raw_threadpool_test.py``).

Loud-failure policy
-------------------

``BranchContext`` itself never validates that the branch exists in any
store — it only validates the *name* (non-empty, no separators).
Adapters that act on the context (e.g. the upcoming ``IVersionedStorePort``
and the ``TripleStoreService`` versioned-store adapter) are responsible
for raising ``BranchNotFoundError`` when an unknown branch reaches
them. This keeps the substrate dependency-free while giving consumers
a single import path for the loud-failure error.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

from .exceptions import BranchValidationError


DEFAULT_BRANCH = "main"
"""Branch name returned by :func:`BranchContext.current` when no
``use(...)`` block is active. Matches the versionstore default."""


_INVALID_NAME_CHARS = ("/", "\\", "\0")
"""Characters that would make a branch name unsafe to use in
filesystem paths, URLs, or message metadata."""


def _validate_branch_name(name: object) -> str:
    """Return ``name`` if it is a syntactically valid branch identifier;
    otherwise raise :class:`BranchValidationError`.

    Validation is purely syntactic — it does not consult any store.
    The rules are deliberately loose so consumers (versionstore,
    HTTP middleware, bus adapters) can layer their own stricter rules
    on top: this function only filters out names that would be
    *universally* unsafe (empty, special-name, path-separator, NUL).
    """
    if not isinstance(name, str):
        raise BranchValidationError(
            f"branch name must be a string, got {type(name).__name__}"
        )
    if not name:
        raise BranchValidationError("branch name must be non-empty")
    if name in (".", ".."):
        raise BranchValidationError(f"invalid branch name: {name!r}")
    for ch in _INVALID_NAME_CHARS:
        if ch in name:
            raise BranchValidationError(
                f"invalid character {ch!r} in branch name: {name!r}"
            )
    return name


_active_branch: contextvars.ContextVar[str] = contextvars.ContextVar(
    "abi_active_branch", default=DEFAULT_BRANCH
)
"""Process-wide ContextVar carrying the active branch.

Module-private; access it through :class:`BranchContext`. The name
``abi_active_branch`` shows up in tracing tools that introspect
``contextvars`` (e.g. when debugging propagation issues), so it is
deliberately specific."""


class BranchContext:
    """Ambient branch propagation. All methods are static; do not
    instantiate.

    The class exists purely as a namespace — every operation reads or
    writes the module-level :data:`_active_branch` ContextVar. There is
    no instance state, so multiple imports of this module in the same
    process see the same context.
    """

    __slots__ = ()

    def __init__(self) -> None:  # pragma: no cover - never instantiated
        raise TypeError(
            "BranchContext is a namespace; use BranchContext.current() / "
            "BranchContext.use(...) directly"
        )

    @staticmethod
    def current() -> str:
        """Return the active branch name, defaulting to ``"main"``."""
        return _active_branch.get()

    @staticmethod
    @contextmanager
    def use(branch: str) -> Iterator[str]:
        """Set the active branch for the duration of the ``with`` block.

        Yields the validated branch name (handy when the caller wants to
        log or echo it). Restores the previous value on exit, including
        on exception. Reentrant — nested ``use(...)`` blocks stack
        correctly because ``ContextVar.reset`` uses the per-set token
        rather than the previous value.
        """
        validated = _validate_branch_name(branch)
        token = _active_branch.set(validated)
        try:
            yield validated
        finally:
            _active_branch.reset(token)

    @staticmethod
    def is_default() -> bool:
        """True iff the active branch is the default (``"main"``)."""
        return _active_branch.get() == DEFAULT_BRANCH
