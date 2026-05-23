"""Exceptions for the branching subsystem.

These are the *consumer-facing* errors. ``BranchContext`` itself never
raises them — it just hands a string back to the caller. The adapters
that consume the context (versioned store, triple store, etc.) are the
ones that turn a missing branch into a loud failure, per the design
note in spec issue #865 / acceptance issue #877:

> Loud-failure policy: reading from a non-existent branch raises
> ``BranchNotFoundError`` instead of silently falling back to ``main``.
"""

from __future__ import annotations


class BranchValidationError(ValueError):
    """The branch *name* is structurally invalid.

    Raised by ``BranchContext.use(name)`` for empty strings, names
    containing path separators, etc. Validation here is purely
    syntactic; it makes no claim that the branch exists in any store."""


class BranchNotFoundError(LookupError):
    """The branch is structurally valid but does not exist in the store.

    Raised by adapters (not by ``BranchContext``) when the active branch
    is propagated into a read or write that targets a non-existent
    branch. Inheriting ``LookupError`` lets callers handle "missing
    branch" alongside other "missing key" errors generically without
    having to import the branching package.
    """
