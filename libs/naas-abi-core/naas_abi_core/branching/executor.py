"""``BranchAwareThreadPoolExecutor``: ``ThreadPoolExecutor`` that
propagates ``contextvars`` (and therefore the active branch) to worker
threads.

Background
----------

``concurrent.futures.ThreadPoolExecutor`` does *not* propagate
contextvars across ``submit``. A ``BranchContext.use(...)`` block in
the caller has no effect on work running in a worker thread — the
worker sees the default ``"main"`` instead. That silent fallback is
exactly what the loud-failure policy is meant to prevent, so we ship
this drop-in replacement and a repository guard test that fails CI if
the raw class is imported anywhere under ``naas_abi_core/``.

Behavior
--------

On every ``submit(fn, *args, **kwargs)``:

1. ``copy_context()`` snapshots the *submitter's* full context
   (active branch, log fields, OTel baggage, anything else stored in
   ContextVars).
2. The worker thread runs ``ctx.run(fn, *args, **kwargs)`` so the
   submitted callable observes that snapshot.

``map`` is implemented in the stdlib on top of ``submit``, so it
inherits propagation for free. Same for ``concurrent.futures.wait``,
``as_completed``, and the rest of the public surface.

Cost
----

``copy_context()`` is roughly an O(n) shallow copy of the active
ContextVars. In practice that's a handful of nanoseconds, dominated by
the cost of crossing a thread boundary. There is no measurable
overhead vs. raw ``ThreadPoolExecutor`` on real workloads.
"""

from __future__ import annotations

import contextvars
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, TypeVar


_R = TypeVar("_R")


class BranchAwareThreadPoolExecutor(ThreadPoolExecutor):
    """Drop-in replacement for ``ThreadPoolExecutor`` that propagates
    contextvars to worker threads.

    Use it everywhere in ``naas_abi_core`` where you would have used
    the stdlib executor. The constructor signature is unchanged; the
    only behavioral difference is that submitted callables observe the
    submitter's ``BranchContext`` (and any other ContextVar)."""

    def submit(  # type: ignore[override]
        self,
        fn: Callable[..., _R],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Future[_R]:
        """Submit ``fn`` to a worker, capturing the current context.

        The signature mirrors ``ThreadPoolExecutor.submit`` exactly so
        the executor stays drop-in compatible. The override lives only
        in the runtime path; type-checkers see the parent signature.
        """
        ctx = contextvars.copy_context()
        return super().submit(ctx.run, fn, *args, **kwargs)
