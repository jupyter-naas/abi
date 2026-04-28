"""versionstore: a generic, append-only, content-addressed versioned blob store.

The store's contract:
  - Filesystem is the source of truth.
  - SQLite is a rebuildable index over the filesystem.
  - Each revision is stored as a single file named:
        {ts_ns:020d}.{prev_hash}.{content_hash}                  (main branch)
        {ts_ns:020d}.{prev_hash}.{content_hash}.{branch}         (other branches)
    with atomic write via `.tmp` + rename.
  - Payloads are opaque bytes; consumers interpret them.
  - UIDs are opaque strings (UUIDs recommended); consumers map business keys
    to UIDs externally.
  - Namespacing = instantiating multiple `Store(path)` on different roots.
    A `StoreRegistry` is provided for convenience.

This vendored copy adds the Tier-1 A & B scaling improvements from the ABI
branching spec: per-uid and per-(branch, uid) concurrency via a lock-free
write path gated by a UNIQUE(branch, uid, prev_hash) constraint, plus the
minimal branching scaffold (`branches` table, `branch=` argument on
read/write methods, `create_branch`, `list_branches`).

Public API:
    Store              - the versioned, branched blob store
    Revision           - immutable record describing one revision
    StoreRegistry      - thin wrapper for managing multiple named Store instances
    uuid7              - time-ordered UUID v7 generator (stdlib only)
    ConcurrencyConflict - raised on optimistic-write failure
    BranchNotFoundError - raised when targeting an unknown branch
    GENESIS            - sentinel prev_hash for the first revision on a branch
    DEFAULT_BRANCH     - "main"
"""

from .revision import DEFAULT_BRANCH, Revision
from .registry import StoreRegistry
from .store import (
    BranchNotFoundError,
    ConcurrencyConflict,
    DURABILITY_FAST,
    DURABILITY_FULL,
    GENESIS,
    Store,
)
from .uuid7 import uuid7

__all__ = [
    "BranchNotFoundError",
    "ConcurrencyConflict",
    "DEFAULT_BRANCH",
    "DURABILITY_FAST",
    "DURABILITY_FULL",
    "GENESIS",
    "Revision",
    "Store",
    "StoreRegistry",
    "uuid7",
]
