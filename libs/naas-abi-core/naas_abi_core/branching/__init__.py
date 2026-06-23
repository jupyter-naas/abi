"""Branching primitives: context propagation, executors, logging, tracing.

The substrate every branch-aware service in ``naas_abi_core`` consumes.
See spec issue #865 for the architectural motivation and acceptance
issue #877 for this module's specific scope.

Public API
----------

* :class:`BranchContext` — ``current()`` / ``use(name)`` ambient
  branch propagation backed by a ``contextvars.ContextVar``.
* :data:`DEFAULT_BRANCH` — the default branch name (``"main"``).
* :class:`BranchAwareThreadPoolExecutor` — drop-in replacement for
  ``concurrent.futures.ThreadPoolExecutor`` that propagates the
  current context (and therefore the active branch) to worker threads.
* :class:`BranchContextLogFilter` — ``logging.Filter`` that adds a
  ``branch`` attribute to every record.
* :func:`add_branch_to_span` — tag an OpenTelemetry span with the
  active branch (no hard OTel dependency).
* :class:`BranchValidationError` / :class:`BranchNotFoundError` —
  syntactic vs. existential branch errors.
* :data:`HTTP_BRANCH_HEADER` / :data:`BUS_BRANCH_FIELD` — boundary
  propagation conventions.
"""

from __future__ import annotations

from .context import BranchContext, DEFAULT_BRANCH
from .conventions import BUS_BRANCH_FIELD, HTTP_BRANCH_HEADER
from .exceptions import BranchNotFoundError, BranchValidationError
from .executor import BranchAwareThreadPoolExecutor
from .logging import BranchContextLogFilter
from .tracing import DEFAULT_BRANCH_SPAN_ATTRIBUTE, add_branch_to_span

__all__ = [
    "BUS_BRANCH_FIELD",
    "BranchAwareThreadPoolExecutor",
    "BranchContext",
    "BranchContextLogFilter",
    "BranchNotFoundError",
    "BranchValidationError",
    "DEFAULT_BRANCH",
    "DEFAULT_BRANCH_SPAN_ATTRIBUTE",
    "HTTP_BRANCH_HEADER",
    "add_branch_to_span",
]
