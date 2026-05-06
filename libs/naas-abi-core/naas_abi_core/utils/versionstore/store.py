"""Store: append-only, content-addressed versioned blob store with branches.

This is the ABI-vendored copy of versionstore. It adds, on top of upstream:

* **Tier 1 A — per-uid concurrency.** The previous global ``BEGIN IMMEDIATE``
  lock around the read-latest + file-write + insert sequence is gone. Reads
  happen lock-free; the file write happens outside any DB transaction; the
  index INSERT carries a ``UNIQUE(branch, uid, prev_hash)`` constraint that
  acts as the conflict gate. Two writers touching different uids no longer
  serialize through a single store-wide lock.

* **Tier 1 B — per-(branch, uid) concurrency.** The unique constraint includes
  ``branch``, so two writers on different branches touching the same uid don't
  conflict either.

* **Tier 1 C — group commit (opt-in).** Writers can join a small commit
  group whose fsyncs are amortized across the whole batch. Enabled by passing
  ``commit_window_ms > 0`` to the constructor; defaults to off. See
  ``WHITEPAPER.md §11`` for the durability model.

* **Branching DAG.** A ``branches`` table tracks branch identities (parent,
  fork timestamp), mirrored on disk as JSON sidecars under
  ``data/__branches__/`` so ``rebuild_index`` reconstructs the full DAG
  from the filesystem alone. Every revision records its ``branch``;
  ``put / latest / history / get / verify`` accept an optional
  ``branch=`` argument (default ``"main"``). ``"main"`` is seeded
  automatically and behaves byte-for-byte like the upstream store.

* **Fall-through reads.** ``latest`` / ``get`` / ``uids`` / ``uids_at`` on a
  child branch transparently inherit revisions from the parent branch as
  they existed at the fork timestamp, recursively up the DAG. The write
  path stays per-branch (own chains start at ``GENESIS``).

* **``merge`` and ``diff``.** ``Store.diff(a, b)`` returns a per-uid
  snapshot diff that automatically cancels inherited state. ``Store.merge``
  drives a per-uid three-way merge with a caller-supplied resolver and
  produces multi-parent revisions: a normal revision file plus a
  ``.merge`` sidecar holding the second parent's content_hash, indexed
  in a ``merges`` table.

* **``delete_branch``.** Removes the branch's own files, ``.merge``
  sidecars, metadata sidecar, and table rows. Refuses ``main`` and
  refuses if any branch points at the target as parent.

* **Optimistic concurrency.** ``put`` accepts an optional
  ``expected_prev_hash``; if the actual tip has moved, ``ConcurrencyConflict``
  is raised instead of silently retrying.

What is **not** here yet (deferred to follow-up):

* The ``IVersionedStorePort`` (lives in naas-abi-core, not in this library).
* Transitive merges (a grandchild merging back into a grandparent in
  one call). ``merge`` v1 requires ``source.parent == target``.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Iterator

from .revision import (
    BRANCHES_DIRNAME,
    DEFAULT_BRANCH,
    HASH_LEN,
    MERGE_SIDECAR_SUFFIX,
    Revision,
    is_merge_sidecar,
    revision_filename_for_sidecar,
)


GENESIS = "0" * HASH_LEN
"""Sentinel prev_hash for the first revision of any uid on a branch."""

DEFAULT_MAX_RETRIES = 16
DEFAULT_COMMIT_MAX_SIZE = 64
DEFAULT_COMMIT_WINDOW_MS = 0.0  # disabled by default; enable per-deployment

# Durability modes.
#
# On Linux, Windows, and BSD, ``os.fsync(fd)`` already issues a real disk
# barrier — when it returns, the data is on non-volatile storage. The
# ``"full"`` and ``"fast"`` modes are equivalent on those platforms.
#
# On Apple platforms, ``os.fsync(fd)`` only flushes data to the drive
# controller's cache. A power loss between ``fsync`` returning and the
# physical write loses the data. Apple provides ``fcntl(fd, F_FULLFSYNC)``
# to issue a true platter-level barrier; this is what SQLite uses when
# ``PRAGMA fullfsync=ON``. ``"full"`` mode opts in to that on Apple
# platforms; ``"fast"`` mode keeps the platform default (the trade we
# made before this option existed).
DURABILITY_FULL = "full"
"""Durability mode: ``put`` returning success implies durable on disk
across every supported platform. On Apple, uses ``F_FULLFSYNC`` and
``PRAGMA fullfsync=ON``. Slower on macOS, identical to ``fast`` elsewhere."""

DURABILITY_FAST = "fast"
"""Durability mode: uses the platform default ``fsync``. On Apple this
is *not* a real disk barrier — failures may lose recently-acknowledged
writes. Use only when you accept that trade (dev environments, tests,
ephemeral data). Identical to ``full`` on non-Apple platforms."""

_VALID_DURABILITY = (DURABILITY_FULL, DURABILITY_FAST)


def _platform_supports_full_fsync() -> bool:
    """True on Apple platforms where ``fcntl(fd, F_FULLFSYNC)`` is the
    only path to true disk durability."""
    return sys.platform == "darwin"


@dataclass
class _PendingWrite:
    """One write in flight, waiting for durability via the commit path."""

    branch: str
    uid: str
    ts_ns: int
    prev_hash: str
    content_hash: str
    tmp_path: Path
    final_path: Path
    uid_dir: Path
    error: BaseException | None = None


@dataclass
class _CommitGroup:
    """A commit group: zero or more pending writes batched into one fsync.

    The first writer to arrive when no group is open becomes the leader. They
    open a new group with a deadline (``time.monotonic() + window_s``).
    Subsequent writers join as followers and wait for ``done`` to be set.
    The leader sleeps on ``cv`` until either the deadline or
    ``len(members) >= max_size``, then closes the group and runs the batch
    commit. Followers are released when ``done`` is set; if the commit raised,
    the per-member ``error`` field is populated.
    """

    deadline: float
    members: list[_PendingWrite] = field(default_factory=list)
    closed: bool = False
    done: threading.Event = field(default_factory=threading.Event)
"""Default cap on the optimistic-concurrency retry loop in ``put``."""


class ConcurrencyConflict(Exception):
    """Raised when an optimistic write cannot be reconciled with the live tip.

    Two situations raise this:

    1. The caller passed ``expected_prev_hash`` and the actual tip differs.
    2. The retry loop exhausted ``max_retries`` without succeeding.
    """


class BranchNotFoundError(Exception):
    """Raised when an operation targets a branch that does not exist."""


class MergeConflict(Exception):
    """Raised when ``merge`` cannot proceed: ``fast-forward`` strategy was
    requested but a uid required three-way reconciliation, or the resolver
    returned ``None`` for at least one uid under ``three-way``.

    The ``conflicts`` mapping is uid → human-readable reason. ``result``
    is the partial ``MergeResult`` describing what was applied before the
    conflict surfaced (merge is non-atomic per uid by design — fall-through
    reads on the target branch see partial progress, which is fine because
    each uid's revision chain stays valid)."""

    def __init__(self, conflicts: dict[str, str], result: "MergeResult"):
        self.conflicts = conflicts
        self.result = result
        super().__init__(
            f"Merge produced {len(conflicts)} conflict(s): "
            + ", ".join(sorted(conflicts.keys())[:5])
            + ("…" if len(conflicts) > 5 else "")
        )


class MergeStrategy(str, Enum):
    """How ``Store.merge`` reconciles divergent uids.

    * ``FAST_FORWARD`` — only succeeds when every diverging uid has not
      changed on ``target`` since the fork point. Any uid that needs
      three-way reconciliation raises ``MergeConflict`` and the merge
      stops at that uid.
    * ``THREE_WAY`` — calls the caller-provided resolver for every uid
      that diverges on both sides. The resolver returns ``bytes`` to
      apply or ``None`` to flag the uid as conflicted.
    """

    FAST_FORWARD = "fast-forward"
    THREE_WAY = "three-way"


@dataclass(frozen=True)
class BranchDiff:
    """Per-uid divergence between two branches' visible state.

    All three sets are over uids:

    * ``added`` — present on ``a`` (after fall-through), absent on ``b``.
    * ``removed`` — present on ``b`` (after fall-through), absent on ``a``.
    * ``changed`` — present on both with different visible content_hash.

    Inherited state shared via fall-through automatically drops out (both
    sides see the same hash). The result is a snapshot diff, not a
    revision-by-revision diff.
    """

    added: frozenset[str]
    removed: frozenset[str]
    changed: frozenset[str]

    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)


@dataclass
class MergeResult:
    """Outcome of a ``Store.merge`` call.

    All four sets are over uids:

    * ``no_op`` — source and target tips were already identical.
    * ``fast_forwarded`` — target hadn't moved since fork; source's tip
      was applied on target as a new revision (with a ``.merge`` sidecar
      pointing at the source tip).
    * ``three_way_merged`` — the resolver returned bytes that were
      applied on target as a new revision (with a ``.merge`` sidecar).
    * ``conflicts`` — uid → reason. Resolver returned ``None`` (under
      ``three-way``) or a uid required three-way reconciliation under
      ``fast-forward``. The corresponding uids were not modified on target.
    """

    no_op: set[str] = field(default_factory=set)
    fast_forwarded: set[str] = field(default_factory=set)
    three_way_merged: set[str] = field(default_factory=set)
    conflicts: dict[str, str] = field(default_factory=dict)


ConflictResolver = Callable[[str, bytes | None, bytes, bytes], "bytes | None"]
"""Signature: ``resolver(uid, base, source, target) -> bytes | None``.

* ``base`` may be ``None`` if the uid did not exist at the fork point
  (i.e. it was added on both sides after fork).
* Returning ``bytes`` produces a new revision on target.
* Returning ``None`` flags the uid as conflicted; target is unchanged.
"""


class Store:
    """Append-only versioned blob store with branches.

    Layout on disk::

        {root}/
            index.db                                  ← rebuildable SQLite index
            data/
                {uid}/
                    {ts_ns:020d}.{prev_hash}.{content_hash}            ← main
                    {ts_ns:020d}.{prev_hash}.{content_hash}.{branch}   ← other

    Merge revisions add a paired sidecar at ``{filename}.merge`` whose
    content is the second parent's content_hash (64-char hex). The first
    parent is encoded in ``prev_hash`` exactly like a non-merge revision,
    so the per-branch chain stays linear and ``verify`` is unchanged.

    Branch metadata lives in two places:

    * Authoritative on disk under ``data/__branches__/{name}.json``
      (parent, fork_ts_ns, created_at). Written tmp+rename + fsync on
      every ``create_branch`` so a crash leaves either the previous or
      the new content, never partial JSON.
    * Cached in the ``branches`` SQLite table for query speed.

    The filesystem is the source of truth: ``rebuild_index`` nukes the
    SQLite index (revisions, merges, branches) and rebuilds the full
    branch DAG from sidecars + revision filenames. Stores written before
    sidecars existed still rebuild correctly — branches discovered only
    from filenames default to ``parent='main', fork_ts_ns=0``.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        durability: str = DURABILITY_FULL,
        commit_window_ms: float = DEFAULT_COMMIT_WINDOW_MS,
        commit_max_size: int = DEFAULT_COMMIT_MAX_SIZE,
    ):
        """Open a Store at ``root``.

        ``durability`` controls the strength of the on-disk persistence
        guarantee made by ``put``:

        * ``"full"`` (default) — a successful ``put`` implies the revision
          is on non-volatile storage. On Apple platforms this uses
          ``fcntl(fd, F_FULLFSYNC)`` for file syncs and
          ``PRAGMA fullfsync=ON`` + ``synchronous=FULL`` for SQLite. On
          Linux/Windows/BSD this is what ``fsync`` does anyway, so there
          is no extra cost. Recommended for production.
        * ``"fast"`` — uses the platform default ``fsync``. On Apple this
          flushes only to the drive's controller cache, not the platter,
          so a power loss can lose recently-acknowledged writes.
          Identical to ``"full"`` on non-Apple platforms. Use for dev,
          tests, or ephemeral data when you accept the trade.

        ``commit_window_ms`` enables group commit (Tier 1 C):

        * ``0.0`` (default) — solo commit. Each ``put`` does its own fsync
          before returning. Behavior is byte-identical to versions before
          group commit.
        * ``> 0.0`` — group commit. A ``put`` enqueues into a shared commit
          group with a deadline ``commit_window_ms`` milliseconds in the
          future, then blocks until the group's batched fsync completes.
          The first writer to arrive when no group is open becomes the
          leader. The group commits early once it reaches
          ``commit_max_size`` members. Recommended starting values are
          ``commit_window_ms=2.0`` and ``commit_max_size=64`` on workloads
          with many concurrent writers and a non-trivial fsync cost.

        See ``WHITEPAPER.md §3`` and ``§11`` for the full models.
        Per-write durability is preserved across both commit paths:
        ``put`` returns success only after its (solo or group) fsync has
        completed.
        """
        if durability not in _VALID_DURABILITY:
            raise ValueError(
                f"durability must be one of {_VALID_DURABILITY!r}, "
                f"got {durability!r}"
            )

        self.root = Path(root)
        self.data_dir = self.root / "data"
        self.index_path = self.root / "index.db"
        self.root.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)

        self._durability = durability
        # ``_use_full_fsync`` is True only when (a) we're in full mode and
        # (b) the platform actually distinguishes full from fast. On
        # Linux/Windows/BSD ``os.fsync`` already does the right thing,
        # so there's no need to take a different code path.
        self._use_full_fsync = (
            durability == DURABILITY_FULL and _platform_supports_full_fsync()
        )
        if self._use_full_fsync:
            # ``fcntl`` is POSIX-only; ``F_FULLFSYNC`` is Darwin-specific.
            # We import here so the module imports cleanly on Windows and
            # any platform where fcntl/F_FULLFSYNC isn't available.
            import fcntl  # noqa: F401

        # isolation_level=None: we manage transactions explicitly with BEGIN/COMMIT.
        # check_same_thread=False allows multiple threads to share the
        # connection; we serialize access ourselves via ``self._db_lock``.
        # The lock is held only across the SQL call (microseconds), never
        # across the file write + fsync (milliseconds) — that is the whole
        # point of the lock-free retry path.
        self._conn = sqlite3.connect(
            self.index_path,
            isolation_level=None,
            check_same_thread=False,
        )
        self._db_lock = threading.RLock()
        # Per-(branch, uid) lock: serializes writers in this process targeting
        # the same logical entity, so threads don't gratuitously fight for the
        # UNIQUE(branch, uid, prev_hash) slot. Different (branch, uid) pairs
        # take different locks and run in parallel — that is the Tier 1 A&B
        # win at the in-process layer. Cross-process correctness is still
        # guaranteed by the UNIQUE constraint and the retry path.
        self._uid_locks: dict[tuple[str, str], threading.Lock] = {}
        self._uid_locks_guard = threading.Lock()

        # Group commit (Tier 1 C). When ``_commit_window_s == 0`` the path
        # bypasses the group entirely.
        self._commit_window_s = max(0.0, commit_window_ms) / 1000.0
        self._commit_max_size = max(1, commit_max_size)
        self._group_cv = threading.Condition()
        self._current_group: _CommitGroup | None = None
        # Diagnostic counters (read by tests). Atomic increments under
        # ``_group_cv`` for batches; under ``_db_lock`` for solo commits.
        self._batch_count = 0
        self._batched_writes = 0

        with self._db_lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            if durability == DURABILITY_FULL:
                # synchronous=FULL: SQLite fsyncs the WAL after every commit
                # and the database file at every checkpoint. Slightly more
                # syncs than NORMAL; required for "if commit succeeds, it's
                # durable" on every platform.
                self._conn.execute("PRAGMA synchronous=FULL")
                if _platform_supports_full_fsync():
                    # On Apple, escalate the syncs SQLite issues to
                    # F_FULLFSYNC. PRAGMA fullfsync covers per-commit
                    # syncs; checkpoint_fullfsync covers WAL checkpoints.
                    # No-ops on non-Apple platforms.
                    self._conn.execute("PRAGMA fullfsync=ON")
                    self._conn.execute("PRAGMA checkpoint_fullfsync=ON")
            else:
                # Fast mode preserves the previous default behavior.
                self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_schema()
        self._seed_main_branch()

    def _sync_fd(self, fd: int) -> None:
        """Force this file descriptor's data to durable storage.

        On Apple in ``"full"`` mode this issues ``F_FULLFSYNC``, which
        triggers a real platter-level barrier. Everywhere else (and on
        Apple in ``"fast"`` mode) it falls back to ``os.fsync``.
        """
        if self._use_full_fsync:
            import fcntl

            # F_FULLFSYNC: "really really flush all buffers to disk" —
            # see Apple's fcntl(2). Required for true durability on
            # Apple platforms; a no-op concept on Linux/Windows where
            # fsync already provides this guarantee. Looked up via
            # ``getattr`` because the symbol is Darwin-only and would
            # otherwise be a static attribute error on non-Apple
            # type-checks. ``_use_full_fsync`` is only True on Apple,
            # so we know it exists at runtime here.
            f_fullfsync = getattr(fcntl, "F_FULLFSYNC")
            fcntl.fcntl(fd, f_fullfsync)
        else:
            os.fsync(fd)

    def _sync_dir(self, path: Path) -> None:
        """Force a directory's metadata to durable storage. Best-effort:
        platforms that don't support directory fsync silently no-op."""
        try:
            fd = os.open(str(path), os.O_RDONLY)
        except OSError:
            return
        try:
            self._sync_fd(fd)
        except OSError:
            # Windows and some filesystems don't support fsync on directories.
            pass
        finally:
            os.close(fd)

    def _uid_lock(self, branch: str, uid: str) -> threading.Lock:
        """Return the in-process lock for ``(branch, uid)``, creating it on demand."""
        key = (branch, uid)
        with self._uid_locks_guard:
            lock = self._uid_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._uid_locks[key] = lock
            return lock

    # ------------------------------------------------------------------ setup

    def _init_schema(self) -> None:
        with self._db_lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS branches (
                    name        TEXT    PRIMARY KEY,
                    parent      TEXT,
                    fork_ts_ns  INTEGER NOT NULL DEFAULT 0,
                    created_at  INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS revisions (
                    branch        TEXT    NOT NULL DEFAULT 'main',
                    uid           TEXT    NOT NULL,
                    ts_ns         INTEGER NOT NULL,
                    prev_hash     TEXT    NOT NULL,
                    content_hash  TEXT    NOT NULL,
                    PRIMARY KEY (uid, ts_ns, branch),
                    UNIQUE (branch, uid, prev_hash)
                );

                CREATE INDEX IF NOT EXISTS idx_revisions_ts ON revisions(ts_ns);
                CREATE INDEX IF NOT EXISTS idx_revisions_branch_uid
                    ON revisions(branch, uid, ts_ns);

                CREATE TABLE IF NOT EXISTS merges (
                    branch        TEXT    NOT NULL,
                    uid           TEXT    NOT NULL,
                    ts_ns         INTEGER NOT NULL,
                    other_parent  TEXT    NOT NULL,
                    PRIMARY KEY (branch, uid, ts_ns)
                );
                """
            )

    def _seed_main_branch(self) -> None:
        now_ns = time.time_ns()
        with self._db_lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO branches(name, parent, fork_ts_ns, created_at) "
                "VALUES (?, NULL, 0, ?)",
                (DEFAULT_BRANCH, now_ns),
            )
        # Pull the actual created_at back so the on-disk sidecar matches
        # the row that won the INSERT OR IGNORE race.
        with self._db_lock:
            row = self._conn.execute(
                "SELECT created_at FROM branches WHERE name = ?",
                (DEFAULT_BRANCH,),
            ).fetchone()
        created_at = row[0] if row is not None else now_ns
        self._write_branch_sidecar(
            DEFAULT_BRANCH, parent=None, fork_ts_ns=0, created_at=created_at
        )

    # --------------------------------------------------------- branch sidecars

    def _branches_dir(self) -> Path:
        return self.data_dir / BRANCHES_DIRNAME

    def _branch_sidecar_path(self, name: str) -> Path:
        return self._branches_dir() / f"{name}.json"

    def _write_branch_sidecar(
        self,
        name: str,
        *,
        parent: str | None,
        fork_ts_ns: int,
        created_at: int,
    ) -> None:
        """Atomically write the on-disk metadata sidecar for a branch.

        ``rebuild_index`` reads these to reconstruct the branch DAG without
        consulting SQLite. The write is tmp+rename so a crash mid-write
        leaves either the previous content or nothing — never a partial
        JSON document."""
        branches_dir = self._branches_dir()
        branches_dir.mkdir(exist_ok=True)
        path = self._branch_sidecar_path(name)
        tmp = path.with_suffix(path.suffix + ".tmp")
        payload = {
            "parent": parent,
            "fork_ts_ns": fork_ts_ns,
            "created_at": created_at,
        }
        try:
            with open(tmp, "w") as f:
                f.write(json.dumps(payload, sort_keys=True))
                f.flush()
                self._sync_fd(f.fileno())
            os.rename(tmp, path)
            self._sync_dir(branches_dir)
        except Exception:
            _best_effort_unlink(tmp)
            raise

    def _read_branch_sidecar(
        self, name: str
    ) -> tuple[str | None, int, int] | None:
        """Read ``(parent, fork_ts_ns, created_at)`` for ``name``, or ``None``
        if the sidecar is missing or unparseable."""
        path = self._branch_sidecar_path(name)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text())
            parent = data.get("parent")
            fork_ts_ns = int(data["fork_ts_ns"])
            created_at = int(data["created_at"])
            if parent is not None and not isinstance(parent, str):
                return None
            return (parent, fork_ts_ns, created_at)
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _delete_branch_sidecar(self, name: str) -> None:
        _best_effort_unlink(self._branch_sidecar_path(name))

    def close(self) -> None:
        with self._db_lock:
            self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # ------------------------------------------------------------- branches

    def create_branch(
        self, name: str, *, parent: str = DEFAULT_BRANCH
    ) -> None:
        """Register a branch. No data is copied; reads on the new branch fall
        through to ``parent`` at the fork timestamp (so every uid that
        existed on ``parent`` at fork time is visible on the child).

        Parent must exist. Branch name must be valid (no ``.``, no path
        separators, not ``main``-reserved-words, etc — see ``_validate_branch``).
        """
        _validate_branch(name)
        if not self._branch_exists(parent):
            raise BranchNotFoundError(f"Parent branch does not exist: {parent!r}")
        now_ns = time.time_ns()
        with self._db_lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO branches(name, parent, fork_ts_ns, created_at) "
                "VALUES (?, ?, ?, ?)",
                (name, parent, now_ns, now_ns),
            )
        # If a row already existed (re-create is a no-op), keep its
        # fork_ts_ns so the on-disk sidecar reflects the persisted truth.
        meta = self._branch_meta(name)
        if meta is not None:
            actual_parent, fork_ts_ns, created_at = meta
            self._write_branch_sidecar(
                name,
                parent=actual_parent,
                fork_ts_ns=fork_ts_ns,
                created_at=created_at,
            )

    def list_branches(self) -> list[str]:
        with self._db_lock:
            rows = self._conn.execute(
                "SELECT name FROM branches ORDER BY name"
            ).fetchall()
        return [r[0] for r in rows]

    def _branch_exists(self, name: str) -> bool:
        with self._db_lock:
            row = self._conn.execute(
                "SELECT 1 FROM branches WHERE name = ?", (name,)
            ).fetchone()
        return row is not None

    def _branch_meta(self, name: str) -> tuple[str | None, int, int] | None:
        """Return ``(parent, fork_ts_ns, created_at)`` for ``name``, or
        ``None`` if unknown."""
        with self._db_lock:
            row = self._conn.execute(
                "SELECT parent, fork_ts_ns, created_at FROM branches "
                "WHERE name = ?",
                (name,),
            ).fetchone()
        if row is None:
            return None
        return (row[0], int(row[1]), int(row[2]))

    def _ancestor_chain(self, name: str) -> list[str]:
        """Return ``[name, parent, grandparent, …]`` walking up the branch DAG.

        Stops at the first branch with ``parent IS NULL`` (typically ``main``)
        or at an unknown parent. Cycles are guarded by a seen-set.
        """
        chain: list[str] = []
        seen: set[str] = set()
        cursor: str | None = name
        while cursor is not None and cursor not in seen:
            chain.append(cursor)
            seen.add(cursor)
            meta = self._branch_meta(cursor)
            if meta is None:
                break
            cursor = meta[0]
        return chain

    # The fall-through "now" cap. Sentinel "no upper bound" used internally
    # so the recursive resolver can keep narrowing the timestamp ceiling.
    _TS_FOREVER = (1 << 63) - 1

    # ------------------------------------------------------------------ write

    def put(
        self,
        uid: str,
        payload: bytes,
        *,
        branch: str = DEFAULT_BRANCH,
        expected_prev_hash: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> Revision | None:
        """Append a new revision for ``uid`` on ``branch`` with the given payload.

        Returns the newly created ``Revision``, or ``None`` if the payload is
        byte-identical to the current latest revision on this branch (no-op,
        not appended).

        If ``expected_prev_hash`` is given, the call raises
        ``ConcurrencyConflict`` when the actual tip's content_hash differs.
        Use this for compare-and-swap semantics from above the store.

        Concurrency model
        -----------------
        Read-latest is lock-free. The file write + ``fsync`` happens outside
        any SQLite transaction. The INSERT into ``revisions`` is gated by
        ``UNIQUE(branch, uid, prev_hash)``: if a concurrent writer beat us to
        this branch+uid+prev_hash, the INSERT raises ``IntegrityError``, we
        clean up our orphan file, re-read the new tip and retry. ``max_retries``
        bounds the loop.
        """
        _validate_uid(uid)
        _validate_branch(branch)
        if not self._branch_exists(branch):
            raise BranchNotFoundError(f"Branch does not exist: {branch!r}")

        content_hash = hashlib.sha256(payload).hexdigest()
        uid_dir = self.data_dir / uid
        uid_dir.mkdir(exist_ok=True)

        last_seen_prev: str | None = None

        # Serialize in-process writers on this (branch, uid). Other
        # (branch, uid) pairs proceed in parallel.
        with self._uid_lock(branch, uid):
            for _attempt in range(max_retries):
                latest = self._latest_on_branch(uid, branch)

                # Idempotent no-op when current tip already has this content.
                if latest is not None and latest.content_hash == content_hash:
                    return None

                prev_hash = (
                    latest.content_hash if latest is not None else GENESIS
                )

                if (
                    expected_prev_hash is not None
                    and prev_hash != expected_prev_hash
                ):
                    raise ConcurrencyConflict(
                        f"Expected prev_hash={expected_prev_hash!r} on "
                        f"branch={branch!r} uid={uid!r}, found {prev_hash!r}"
                    )

                ts_ns = time.time_ns()
                if latest is not None and ts_ns <= latest.ts_ns:
                    ts_ns = latest.ts_ns + 1

                tentative = Revision(
                    uid=uid,
                    ts_ns=ts_ns,
                    prev_hash=prev_hash,
                    content_hash=content_hash,
                    path=uid_dir / "_unset_",
                    branch=branch,
                )
                filename = tentative.filename
                final_path = uid_dir / filename
                tmp_path = uid_dir / (filename + ".tmp")

                # Write the tmp file (no fsync yet — that happens during
                # commit, possibly batched with other writers in the same
                # group). The flush gets the bytes into the OS page cache;
                # fsync makes them durable.
                try:
                    with open(tmp_path, "wb") as f:
                        f.write(payload)
                        f.flush()
                except Exception:
                    _best_effort_unlink(tmp_path)
                    raise

                pending = _PendingWrite(
                    branch=branch,
                    uid=uid,
                    ts_ns=ts_ns,
                    prev_hash=prev_hash,
                    content_hash=content_hash,
                    tmp_path=tmp_path,
                    final_path=final_path,
                    uid_dir=uid_dir,
                )

                # Block until the write is durable (fsync'd, renamed,
                # indexed) — either via the group commit path or solo,
                # depending on configuration.
                if self._commit_window_s > 0.0:
                    self._submit_to_group(pending)
                else:
                    self._commit_solo(pending)

                if pending.error is None:
                    return Revision(
                        uid=uid,
                        ts_ns=ts_ns,
                        prev_hash=prev_hash,
                        content_hash=content_hash,
                        path=final_path,
                        branch=branch,
                    )

                # The commit path raises IntegrityError when a cross-process
                # writer landed a revision at the same (branch, uid,
                # prev_hash). Clean up has already happened; we just retry.
                if isinstance(pending.error, sqlite3.IntegrityError):
                    if expected_prev_hash is not None:
                        raise ConcurrencyConflict(
                            f"Concurrent writer changed tip on "
                            f"branch={branch!r} uid={uid!r}"
                        )
                    last_seen_prev = prev_hash
                    continue

                # Any other error from the commit path is fatal — re-raise.
                raise pending.error

        raise ConcurrencyConflict(
            f"Failed to write after {max_retries} retries on "
            f"branch={branch!r} uid={uid!r} (last seen prev_hash={last_seen_prev!r})"
        )

    # ----------------------------------------------------------- commit path

    def _commit_solo(self, w: _PendingWrite) -> None:
        """Solo commit path (group commit disabled): single-writer fsync,
        rename, dir-fsync, INSERT. Errors land in ``w.error``.

        Uses ``self._sync_fd`` so durability mode (full/fast) is honored.
        """
        try:
            with open(w.tmp_path, "rb+") as f:
                self._sync_fd(f.fileno())
            os.rename(w.tmp_path, w.final_path)
            self._sync_dir(w.uid_dir)
        except Exception as e:
            _best_effort_unlink(w.tmp_path)
            w.error = e
            return

        try:
            with self._db_lock:
                self._conn.execute(
                    "INSERT INTO revisions"
                    "(branch, uid, ts_ns, prev_hash, content_hash) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (w.branch, w.uid, w.ts_ns, w.prev_hash, w.content_hash),
                )
        except sqlite3.IntegrityError as e:
            _best_effort_unlink(w.final_path)
            w.error = e

    def _submit_to_group(self, w: _PendingWrite) -> None:
        """Group commit path: enqueue, lead-or-follow, return when durable.

        The first writer to find no open group becomes the leader. Followers
        join the open group and wait for the leader to drive the commit.
        Failures (per-member, e.g. UNIQUE conflict) land in ``w.error``;
        catastrophic failures (e.g. fsync errno) propagate to every member
        of the affected group via ``error``.
        """
        is_leader = False
        with self._group_cv:
            group = self._current_group
            # Open a new group if (a) none is open, (b) the current one
            # has been closed by its leader, or (c) the current one is
            # already at the size cap. Case (c) makes the cap hard:
            # without it, a follower arriving between the leader's
            # notify and its re-acquisition of the cv could squeeze
            # past the limit.
            if (
                group is None
                or group.closed
                or len(group.members) >= self._commit_max_size
            ):
                group = _CommitGroup(
                    deadline=time.monotonic() + self._commit_window_s
                )
                self._current_group = group
                is_leader = True
            group.members.append(w)
            if len(group.members) >= self._commit_max_size:
                # Wake the leader if it was sleeping on the deadline.
                self._group_cv.notify_all()

        if is_leader:
            self._lead_commit(group)
        else:
            group.done.wait()

    def _lead_commit(self, group: _CommitGroup) -> None:
        """Wait for the deadline or size cap, then commit the group."""
        with self._group_cv:
            while not group.closed:
                remaining = group.deadline - time.monotonic()
                if remaining <= 0 or len(group.members) >= self._commit_max_size:
                    break
                self._group_cv.wait(timeout=remaining)
            group.closed = True
            if self._current_group is group:
                self._current_group = None
            members = list(group.members)

        try:
            self._commit_batch(members)
        finally:
            # Whatever happened, release every follower so they can read
            # their own per-member ``error`` (or success).
            group.done.set()

    def _commit_batch(self, members: list[_PendingWrite]) -> None:
        """Durably persist a batch of pending writes.

        Steps, in order:

        1. fsync each tmp file. The kernel typically batches concurrent
           fsyncs at the journal layer, so even sequential fsyncs in this
           loop are amortized at the device level.
        2. Sort members by ``ts_ns`` and rename in chain order so that a
           crash mid-rename leaves a valid prefix on disk (every renamed
           file's prev_hash points to an already-renamed predecessor).
        3. Dedup ``uid_dir`` and fsync each unique directory once.
        4. Insert all rows in a single SQLite transaction, with a savepoint
           around each row so a single UNIQUE conflict only fails that one
           member rather than the whole batch. Conflicting rows have their
           orphan files cleaned up here.
        """
        if not members:
            return

        # 1. fsync each tmp file (honoring durability mode).
        for w in members:
            if w.error is not None:
                continue
            try:
                fd = os.open(str(w.tmp_path), os.O_RDONLY)
                try:
                    self._sync_fd(fd)
                finally:
                    os.close(fd)
            except OSError as e:
                _best_effort_unlink(w.tmp_path)
                w.error = e

        # 2. Sort by ts_ns, then rename in order. (Within the same
        # (branch, uid), ts_ns is monotonic — chains stay valid on a
        # partial-rename crash.)
        members_sorted = sorted(members, key=lambda x: x.ts_ns)
        for w in members_sorted:
            if w.error is not None:
                continue
            try:
                os.rename(w.tmp_path, w.final_path)
            except OSError as e:
                _best_effort_unlink(w.tmp_path)
                w.error = e

        # 3. dir fsync, deduped per uid_dir (honoring durability mode).
        uniq_dirs = {w.uid_dir for w in members if w.error is None}
        for d in uniq_dirs:
            self._sync_dir(d)

        # 4. Batched INSERTs in one transaction with per-row savepoints.
        with self._db_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                for idx, w in enumerate(members):
                    if w.error is not None:
                        continue
                    sp = f"sp_{idx}"
                    self._conn.execute(f"SAVEPOINT {sp}")
                    try:
                        self._conn.execute(
                            "INSERT INTO revisions"
                            "(branch, uid, ts_ns, prev_hash, content_hash) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (
                                w.branch,
                                w.uid,
                                w.ts_ns,
                                w.prev_hash,
                                w.content_hash,
                            ),
                        )
                        self._conn.execute(f"RELEASE SAVEPOINT {sp}")
                    except sqlite3.IntegrityError as e:
                        self._conn.execute(f"ROLLBACK TO SAVEPOINT {sp}")
                        self._conn.execute(f"RELEASE SAVEPOINT {sp}")
                        _best_effort_unlink(w.final_path)
                        w.error = e
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                # Tag every member that was about to be inserted as failed
                # so followers see the error.
                for w in members:
                    if w.error is None:
                        w.error = RuntimeError(
                            "group commit aborted before insert succeeded"
                        )
                raise

        # Diagnostics: tests use these to verify batching is happening.
        with self._group_cv:
            self._batch_count += 1
            self._batched_writes += len(members)

    # ------------------------------------------------------------------ read

    def get(
        self,
        uid: str,
        at: datetime | None = None,
        *,
        branch: str = DEFAULT_BRANCH,
    ) -> bytes | None:
        """Return the payload bytes of ``uid`` on ``branch`` at time ``at``
        (latest if ``None``).

        Returns ``None`` if no revision exists on this branch at or before
        ``at``. An empty ``bytes`` return value means the revision exists and
        is intentionally empty.
        """
        rev = self.latest(uid, at, branch=branch)
        return rev.read() if rev is not None else None

    def latest(
        self,
        uid: str,
        at: datetime | None = None,
        *,
        branch: str = DEFAULT_BRANCH,
    ) -> Revision | None:
        """Return the latest visible ``Revision`` for ``uid`` on ``branch`` at
        ``at``, or ``None``.

        "Visible" means: own-branch revisions are checked first; if none
        match, fall through to the parent branch capped at the fork
        timestamp, recursively up the branch DAG. This mirrors how reads
        on a fresh feature branch see whatever existed on its parent at
        the moment the branch was created."""
        _validate_uid(uid)
        _validate_branch(branch)
        ts_limit = self._TS_FOREVER if at is None else _dt_to_ns(at)
        return self._resolve_latest_walking(uid, branch, ts_limit)

    def _resolve_latest_walking(
        self, uid: str, branch: str, ts_limit: int
    ) -> Revision | None:
        """Walk ``branch`` and its ancestors looking for the most recent
        revision of ``uid`` at or before ``ts_limit``."""
        seen: set[str] = set()
        cursor: str | None = branch
        cap = ts_limit
        while cursor is not None and cursor not in seen:
            seen.add(cursor)
            rev = self._latest_own(uid, cursor, cap)
            if rev is not None:
                return rev
            meta = self._branch_meta(cursor)
            if meta is None:
                return None
            parent, fork_ts_ns, _ = meta
            if parent is None:
                return None
            # Looking up the parent: only revisions that existed at
            # fork-time are inherited.
            cap = min(cap, fork_ts_ns)
            cursor = parent
        return None

    def _latest_own(
        self, uid: str, branch: str, ts_limit: int
    ) -> Revision | None:
        """Latest revision of ``uid`` written *on* ``branch`` (no fall-through),
        capped at ``ts_limit`` (inclusive)."""
        with self._db_lock:
            row = self._conn.execute(
                "SELECT ts_ns, prev_hash, content_hash FROM revisions "
                "WHERE branch = ? AND uid = ? AND ts_ns <= ? "
                "ORDER BY ts_ns DESC LIMIT 1",
                (branch, uid, ts_limit),
            ).fetchone()
        if row is None:
            return None
        return self._build_revision(uid, *row, branch=branch)

    def _latest_on_branch(self, uid: str, branch: str) -> Revision | None:
        """Internal hot-path: latest *own-branch* tip, validation skipped.

        Used by the write path: ``put`` chains a new revision off the
        previous own write on the same branch, never off an inherited tip.
        Inheritance is a read-time concern (see ``_resolve_latest_walking``).
        """
        with self._db_lock:
            row = self._conn.execute(
                "SELECT ts_ns, prev_hash, content_hash FROM revisions "
                "WHERE branch = ? AND uid = ? ORDER BY ts_ns DESC LIMIT 1",
                (branch, uid),
            ).fetchone()
        if row is None:
            return None
        return self._build_revision(uid, *row, branch=branch)

    # ----------------------------------------------------------- diff / merge

    def diff(self, a: str, b: str) -> BranchDiff:
        """Snapshot diff between two branches' visible state.

        Compares ``_resolve_latest_walking`` for every uid visible on
        either branch. Inherited state shared via fall-through automatically
        cancels out (both sides resolve to the same content_hash). See
        ``BranchDiff``."""
        _validate_branch(a)
        _validate_branch(b)
        if not self._branch_exists(a):
            raise BranchNotFoundError(f"Branch does not exist: {a!r}")
        if not self._branch_exists(b):
            raise BranchNotFoundError(f"Branch does not exist: {b!r}")
        a_uids = self._visible_uids(a, self._TS_FOREVER)
        b_uids = self._visible_uids(b, self._TS_FOREVER)
        added: set[str] = set()
        removed: set[str] = set()
        changed: set[str] = set()
        for uid in a_uids | b_uids:
            ra = self._resolve_latest_walking(uid, a, self._TS_FOREVER)
            rb = self._resolve_latest_walking(uid, b, self._TS_FOREVER)
            if ra is None and rb is not None:
                removed.add(uid)
            elif rb is None and ra is not None:
                added.add(uid)
            elif (
                ra is not None
                and rb is not None
                and ra.content_hash != rb.content_hash
            ):
                changed.add(uid)
        return BranchDiff(
            added=frozenset(added),
            removed=frozenset(removed),
            changed=frozenset(changed),
        )

    def merge(
        self,
        source: str,
        target: str,
        *,
        resolver: ConflictResolver | None = None,
        strategy: MergeStrategy = MergeStrategy.THREE_WAY,
    ) -> MergeResult:
        """Merge ``source`` into ``target``, writing multi-parent revisions.

        Preconditions:

        * Both branches exist.
        * ``source != target``.
        * ``source.parent == target``. (V1 limitation: only single-hop
          merges. Transitive merges — merging a grandchild into a
          grandparent — are a follow-up that requires a real common-ancestor
          walk. Raises ``ValueError`` otherwise.)

        Per-uid algorithm with ``base = target's view of uid at source.fork_ts_ns``:

        * ``source_tip == target_tip`` → ``no_op``.
        * Source added a uid that target lacks → ``fast_forwarded``.
        * ``source_tip == base`` → target changed alone, ``no_op``.
        * ``target_tip == base`` → source changed alone, ``fast_forwarded``.
        * Both diverged from base → ``three_way_merged`` (resolver) or
          ``conflicts`` (resolver returned ``None``, or ``FAST_FORWARD``
          strategy).

        Each ``fast_forwarded`` / ``three_way_merged`` uid produces one new
        revision on ``target`` (chained off the last own-target tip via the
        regular write path) plus a ``.merge`` sidecar pointing at
        ``source_tip.content_hash``. The sidecar is also recorded in the
        ``merges`` index table.

        Merge is non-atomic across uids by design: each uid's write is
        independently durable. A crash mid-merge leaves a valid prefix on
        target (every applied uid is fully written before the next is
        attempted). Resume by re-running ``merge`` — already-applied uids
        will fall into the ``no_op`` bucket.
        """
        _validate_branch(source)
        _validate_branch(target)
        if source == target:
            raise ValueError("source and target must differ")
        for b in (source, target):
            if not self._branch_exists(b):
                raise BranchNotFoundError(f"Branch does not exist: {b!r}")
        source_meta = self._branch_meta(source)
        if source_meta is None or source_meta[0] != target:
            raise ValueError(
                f"merge v1 requires source.parent == target; "
                f"{source!r}.parent = {source_meta[0] if source_meta else None!r}"
            )
        fork_ts_ns = source_meta[1]

        # Union of uids visible on either side. Order is sorted so merge
        # progress is deterministic across runs (helps reasoning about
        # crash recovery).
        all_uids = sorted(
            self._visible_uids(source, self._TS_FOREVER)
            | self._visible_uids(target, self._TS_FOREVER)
        )
        result = MergeResult()
        for uid in all_uids:
            source_tip = self._resolve_latest_walking(
                uid, source, self._TS_FOREVER
            )
            target_tip = self._resolve_latest_walking(
                uid, target, self._TS_FOREVER
            )
            base_tip = self._resolve_latest_walking(uid, target, fork_ts_ns)

            if source_tip is None:
                # Nothing to merge from source for this uid (it only
                # exists on target post-fork, or doesn't exist at all).
                continue

            if (
                target_tip is not None
                and source_tip.content_hash == target_tip.content_hash
            ):
                result.no_op.add(uid)
                continue

            base_hash = base_tip.content_hash if base_tip is not None else None
            target_hash = target_tip.content_hash if target_tip is not None else None

            if target_hash == base_hash:
                # Target hasn't moved since fork — fast-forward apply
                # source's bytes on target.
                source_payload = source_tip.read()
                self._apply_merge(
                    uid, target, source_payload, source_tip.content_hash
                )
                result.fast_forwarded.add(uid)
                continue

            if source_tip.content_hash == base_hash:
                # Source hasn't moved since fork — target's own work wins.
                result.no_op.add(uid)
                continue

            # Both sides moved. Three-way territory.
            if strategy is MergeStrategy.FAST_FORWARD:
                reason = (
                    f"uid {uid!r} requires three-way merge but strategy "
                    f"is fast-forward (base={base_hash!r}, "
                    f"source={source_tip.content_hash!r}, "
                    f"target={target_hash!r})"
                )
                result.conflicts[uid] = reason
                # Stop on first ff failure — semantics of fast-forward are
                # all-or-nothing per the strategy contract.
                raise MergeConflict({uid: reason}, result)

            if resolver is None:
                reason = "three-way merge needed but no resolver provided"
                result.conflicts[uid] = reason
                continue

            base_payload = base_tip.read() if base_tip is not None else None
            assert target_tip is not None  # target_hash != base_hash → tip exists
            target_payload = target_tip.read()
            source_payload = source_tip.read()

            resolved = resolver(uid, base_payload, source_payload, target_payload)
            if resolved is None:
                result.conflicts[uid] = "resolver returned None"
                continue
            if resolved == target_payload:
                # Resolver said "keep target as-is" — no new revision.
                result.no_op.add(uid)
                continue

            self._apply_merge(uid, target, resolved, source_tip.content_hash)
            result.three_way_merged.add(uid)

        if result.conflicts:
            raise MergeConflict(dict(result.conflicts), result)
        return result

    def _apply_merge(
        self,
        uid: str,
        target: str,
        payload: bytes,
        other_parent: str,
    ) -> None:
        """Write a new revision on ``target`` plus its ``.merge`` sidecar.

        The revision is written through the regular ``put`` path so it
        participates in the same concurrency, durability, and idempotency
        rules. The sidecar is then written and the ``merges`` index row
        inserted; both are durable before this returns.

        If ``put`` returns ``None`` (the resolved payload exactly matches
        target's own latest tip), no sidecar is written — there is no
        new revision to attach it to."""
        rev = self.put(uid, payload, branch=target)
        if rev is None:
            return
        self._write_merge_sidecar(rev, other_parent)

    def _write_merge_sidecar(self, rev: Revision, other_parent: str) -> None:
        if len(other_parent) != HASH_LEN:
            raise ValueError(
                f"other_parent must be a {HASH_LEN}-char hex hash, got "
                f"{len(other_parent)} chars"
            )
        sidecar = rev.merge_sidecar_path
        tmp = sidecar.parent / (sidecar.name + ".tmp")
        try:
            with open(tmp, "w") as f:
                f.write(other_parent)
                f.flush()
                self._sync_fd(f.fileno())
            os.rename(tmp, sidecar)
            self._sync_dir(rev.path.parent)
        except Exception:
            _best_effort_unlink(tmp)
            raise
        with self._db_lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO merges"
                "(branch, uid, ts_ns, other_parent) VALUES (?, ?, ?, ?)",
                (rev.branch, rev.uid, rev.ts_ns, other_parent),
            )

    # --------------------------------------------------------- delete branch

    def delete_branch(self, name: str) -> None:
        """Remove ``name`` and every artifact it owns.

        Refuses to delete ``main``. Refuses if any branch's ``parent``
        points at ``name`` — delete the children first, or rebase them.

        Removes:

        * Every revision file written on this branch (``data/{uid}/…{branch}``).
        * Every ``.merge`` sidecar on those revisions.
        * The branch's metadata sidecar (``data/__branches__/{name}.json``).
        * The corresponding rows in ``revisions``, ``merges``, ``branches``.

        Other branches' inherited views are unaffected: fall-through walks
        from child to parent, never the other way, so deleting a leaf
        branch can never strand an ancestor's reads. After ``delete_branch``,
        ``rebuild_index`` produces no orphaned references — that is the
        reachability-GC contract (issue #876)."""
        _validate_branch(name)
        if name == DEFAULT_BRANCH:
            raise ValueError("Cannot delete the main branch")
        if not self._branch_exists(name):
            raise BranchNotFoundError(f"Branch does not exist: {name!r}")
        with self._db_lock:
            children = self._conn.execute(
                "SELECT name FROM branches WHERE parent = ?", (name,)
            ).fetchall()
        if children:
            child_names = ", ".join(repr(c[0]) for c in children)
            raise ValueError(
                f"Branch {name!r} has child branches: {child_names}. "
                "Delete or re-parent them first."
            )

        # Collect every (uid, ts_ns, prev_hash, content_hash) on the branch
        # so we can remove the underlying files. Done before the SQL
        # delete so the rows are still available.
        with self._db_lock:
            rows = self._conn.execute(
                "SELECT uid, ts_ns, prev_hash, content_hash FROM revisions "
                "WHERE branch = ?",
                (name,),
            ).fetchall()
        for uid, ts_ns, prev_hash, content_hash in rows:
            rev = self._build_revision(
                uid, ts_ns, prev_hash, content_hash, branch=name
            )
            _best_effort_unlink(rev.merge_sidecar_path)
            _best_effort_unlink(rev.path)

        with self._db_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    "DELETE FROM merges WHERE branch = ?", (name,)
                )
                self._conn.execute(
                    "DELETE FROM revisions WHERE branch = ?", (name,)
                )
                self._conn.execute(
                    "DELETE FROM branches WHERE name = ?", (name,)
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        self._delete_branch_sidecar(name)
        # Drop the per-(branch, uid) locks for the dead branch so they
        # don't accumulate forever on long-lived stores.
        with self._uid_locks_guard:
            for key in [k for k in self._uid_locks if k[0] == name]:
                self._uid_locks.pop(key, None)

    def history(
        self, uid: str, *, branch: str = DEFAULT_BRANCH
    ) -> Iterator[Revision]:
        """Yield all revisions for ``uid`` on ``branch`` in chronological
        order (oldest first)."""
        _validate_uid(uid)
        _validate_branch(branch)
        with self._db_lock:
            rows = self._conn.execute(
                "SELECT ts_ns, prev_hash, content_hash FROM revisions "
                "WHERE branch = ? AND uid = ? ORDER BY ts_ns ASC",
                (branch, uid),
            ).fetchall()
        for row in rows:
            yield self._build_revision(uid, *row, branch=branch)

    def uids(self, *, branch: str = DEFAULT_BRANCH) -> Iterator[str]:
        """Yield every uid visible on ``branch`` (own writes plus inherited
        uids from ancestors at their respective fork timestamps)."""
        _validate_branch(branch)
        for uid in sorted(self._visible_uids(branch, self._TS_FOREVER)):
            yield uid

    def uids_at(
        self,
        at: datetime | None = None,
        *,
        branch: str = DEFAULT_BRANCH,
    ) -> Iterator[tuple[str, Revision]]:
        """Yield ``(uid, latest_revision)`` for every uid visible on
        ``branch`` at or before ``at`` (own writes plus inherited)."""
        _validate_branch(branch)
        ts_limit = self._TS_FOREVER if at is None else _dt_to_ns(at)
        for uid in sorted(self._visible_uids(branch, ts_limit)):
            rev = self._resolve_latest_walking(uid, branch, ts_limit)
            if rev is not None:
                yield uid, rev

    def _visible_uids(self, branch: str, ts_limit: int) -> set[str]:
        """Set of uids reachable on ``branch`` at or before ``ts_limit``,
        walking the parent chain at each fork timestamp."""
        visible: set[str] = set()
        seen: set[str] = set()
        cursor: str | None = branch
        cap = ts_limit
        while cursor is not None and cursor not in seen:
            seen.add(cursor)
            with self._db_lock:
                rows = self._conn.execute(
                    "SELECT DISTINCT uid FROM revisions "
                    "WHERE branch = ? AND ts_ns <= ?",
                    (cursor, cap),
                ).fetchall()
            for (uid,) in rows:
                visible.add(uid)
            meta = self._branch_meta(cursor)
            if meta is None:
                break
            parent, fork_ts_ns, _ = meta
            if parent is None:
                break
            cap = min(cap, fork_ts_ns)
            cursor = parent
        return visible

    # ---------------------------------------------------------- integrity ops

    def verify(self, uid: str, *, branch: str = DEFAULT_BRANCH) -> bool:
        """Verify the Merkle chain and content hashes for ``uid`` on ``branch``.

        Returns ``True`` iff every revision's content hashes to its declared
        hash, and every ``prev_hash`` matches the previous revision's
        ``content_hash`` (with ``GENESIS`` for the first).
        """
        expected_prev = GENESIS
        count = 0
        for rev in self.history(uid, branch=branch):
            count += 1
            if rev.prev_hash != expected_prev:
                return False
            if not rev.path.is_file():
                return False
            actual = hashlib.sha256(rev.path.read_bytes()).hexdigest()
            if actual != rev.content_hash:
                return False
            expected_prev = rev.content_hash
        if count > 0:
            return True
        # No revisions for this (uid, branch). That's a valid state iff the
        # uid directory has no files for this branch.
        uid_dir = self.data_dir / uid
        if not uid_dir.exists():
            return True
        for f in uid_dir.iterdir():
            if not f.is_file() or f.name.endswith(".tmp"):
                continue
            if is_merge_sidecar(f.name):
                continue
            try:
                rev = Revision.parse_filename(uid, f.name, uid_dir)
            except ValueError:
                continue
            if rev.branch == branch:
                return False
        return True

    def rebuild_index(self) -> None:
        """Drop and repopulate the SQLite index from the filesystem.

        Orphan ``.tmp`` files are deleted. Unparseable filenames are skipped
        silently. Branch metadata is reconstructed in two stages:

        1. ``data/__branches__/{name}.json`` sidecars are read first — they
           carry the authoritative ``(parent, fork_ts_ns, created_at)`` so
           the branch DAG fully rebuilds without SQLite.
        2. Any branch present in revision filenames but missing a sidecar
           falls back to ``parent='main', fork_ts_ns=0`` (legacy behavior,
           preserved for stores written before the sidecar grammar shipped).

        Merge revisions: a revision file accompanied by a ``.merge`` sidecar
        gets a row in the ``merges`` table whose ``other_parent`` is the
        sidecar's content. Sidecar files without a paired revision are
        deleted as orphans.
        """
        with self._db_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute("DELETE FROM revisions")
                self._conn.execute("DELETE FROM merges")
                discovered_branches: set[str] = {DEFAULT_BRANCH}
                # (branch, uid, prev_hash)
                seen_keys: set[tuple[str, str, str]] = set()

                if self.data_dir.exists():
                    for uid_dir in self.data_dir.iterdir():
                        if not uid_dir.is_dir():
                            continue
                        if uid_dir.name == BRANCHES_DIRNAME:
                            continue
                        uid = uid_dir.name
                        revs: list[Revision] = []
                        sidecars: dict[str, Path] = {}
                        for f in uid_dir.iterdir():
                            if not f.is_file():
                                continue
                            if f.name.endswith(".tmp"):
                                _best_effort_unlink(f)
                                continue
                            if is_merge_sidecar(f.name):
                                rev_filename = revision_filename_for_sidecar(f.name)
                                sidecars[rev_filename] = f
                                continue
                            try:
                                revs.append(
                                    Revision.parse_filename(uid, f.name, uid_dir)
                                )
                            except ValueError:
                                continue
                        revs.sort(key=lambda r: r.ts_ns)
                        rev_filenames: set[str] = set()
                        for rev in revs:
                            discovered_branches.add(rev.branch)
                            key = (rev.branch, rev.uid, rev.prev_hash)
                            if key in seen_keys:
                                # Two files share (branch, uid, prev_hash).
                                # Keep the earliest (already inserted), drop
                                # the rest along with any sidecar.
                                _best_effort_unlink(
                                    rev.path.parent
                                    / (rev.path.name + MERGE_SIDECAR_SUFFIX)
                                )
                                _best_effort_unlink(rev.path)
                                continue
                            seen_keys.add(key)
                            rev_filenames.add(rev.path.name)
                            self._conn.execute(
                                "INSERT INTO revisions"
                                "(branch, uid, ts_ns, prev_hash, content_hash) "
                                "VALUES (?, ?, ?, ?, ?)",
                                (
                                    rev.branch,
                                    rev.uid,
                                    rev.ts_ns,
                                    rev.prev_hash,
                                    rev.content_hash,
                                ),
                            )
                            sidecar_path = sidecars.pop(rev.path.name, None)
                            if sidecar_path is not None:
                                other_parent = _read_sidecar_hash(sidecar_path)
                                if other_parent is not None:
                                    self._conn.execute(
                                        "INSERT INTO merges"
                                        "(branch, uid, ts_ns, other_parent) "
                                        "VALUES (?, ?, ?, ?)",
                                        (
                                            rev.branch,
                                            rev.uid,
                                            rev.ts_ns,
                                            other_parent,
                                        ),
                                    )
                                else:
                                    # Unreadable / malformed sidecar — drop it.
                                    _best_effort_unlink(sidecar_path)
                        # Any sidecar whose paired revision was dropped
                        # (or never existed) is an orphan — clean it up.
                        for orphan in sidecars.values():
                            _best_effort_unlink(orphan)

                # Stage 1: read on-disk branch sidecars (authoritative).
                branches_dir = self._branches_dir()
                sidecar_branches: dict[str, tuple[str | None, int, int]] = {}
                if branches_dir.is_dir():
                    for f in branches_dir.iterdir():
                        if not f.is_file() or not f.name.endswith(".json"):
                            continue
                        if f.name.endswith(".json.tmp"):
                            _best_effort_unlink(f)
                            continue
                        name = f.name[: -len(".json")]
                        try:
                            _validate_branch(name)
                        except ValueError:
                            continue
                        meta = self._read_branch_sidecar(name)
                        if meta is not None:
                            sidecar_branches[name] = meta
                            discovered_branches.add(name)

                # Wipe and re-seed branches table from sidecars + filenames.
                self._conn.execute(
                    "DELETE FROM branches WHERE name != ?", (DEFAULT_BRANCH,)
                )
                # Ensure main exists (sidecar-or-default).
                if DEFAULT_BRANCH in sidecar_branches:
                    parent, fork_ts_ns, created_at = sidecar_branches[DEFAULT_BRANCH]
                    self._conn.execute(
                        "INSERT OR REPLACE INTO branches"
                        "(name, parent, fork_ts_ns, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (DEFAULT_BRANCH, parent, fork_ts_ns, created_at),
                    )
                else:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO branches"
                        "(name, parent, fork_ts_ns, created_at) "
                        "VALUES (?, NULL, 0, ?)",
                        (DEFAULT_BRANCH, time.time_ns()),
                    )
                now_ns = time.time_ns()
                for b in discovered_branches:
                    if b == DEFAULT_BRANCH:
                        continue
                    if b in sidecar_branches:
                        parent, fork_ts_ns, created_at = sidecar_branches[b]
                        self._conn.execute(
                            "INSERT OR REPLACE INTO branches"
                            "(name, parent, fork_ts_ns, created_at) "
                            "VALUES (?, ?, ?, ?)",
                            (b, parent, fork_ts_ns, created_at),
                        )
                    else:
                        self._conn.execute(
                            "INSERT OR IGNORE INTO branches"
                            "(name, parent, fork_ts_ns, created_at) "
                            "VALUES (?, ?, 0, ?)",
                            (b, DEFAULT_BRANCH, now_ns),
                        )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    # ---------------------------------------------------------------- helpers

    def _build_revision(
        self,
        uid: str,
        ts_ns: int,
        prev_hash: str,
        content_hash: str,
        *,
        branch: str = DEFAULT_BRANCH,
    ) -> Revision:
        # Two-step build so we can derive the on-disk filename via Revision.filename.
        scratch = Revision(
            uid=uid,
            ts_ns=ts_ns,
            prev_hash=prev_hash,
            content_hash=content_hash,
            path=self.data_dir / uid / "_unset_",
            branch=branch,
        )
        return Revision(
            uid=uid,
            ts_ns=ts_ns,
            prev_hash=prev_hash,
            content_hash=content_hash,
            path=self.data_dir / uid / scratch.filename,
            branch=branch,
        )


# ------------------------------------------------------------------ utilities


_RESERVED_BRANCH_NAMES = frozenset({"merge"})
"""Branch names that would collide with the merge-sidecar grammar.

A merge sidecar on the main branch is named ``{ts}.{prev}.{content}.merge``
— four dot-separated parts, indistinguishable from a non-main revision on
a branch named ``merge``. Reserving the literal ``"merge"`` keeps the
filename grammar a function of the file alone."""

_RESERVED_UID_NAMES = frozenset({BRANCHES_DIRNAME})
"""UIDs that would collide with reserved subdirectories under ``data/``."""


def _validate_uid(uid: str) -> None:
    if not isinstance(uid, str) or not uid:
        raise ValueError("uid must be a non-empty string")
    if "/" in uid or "\\" in uid or "\0" in uid or uid in (".", ".."):
        raise ValueError(f"Invalid uid: {uid!r}")
    if uid in _RESERVED_UID_NAMES:
        raise ValueError(f"Reserved uid: {uid!r}")


def _validate_branch(name: str) -> None:
    if not isinstance(name, str) or not name:
        raise ValueError("branch name must be a non-empty string")
    if name in (".", ".."):
        raise ValueError(f"Invalid branch name: {name!r}")
    # Branch names appear in filenames as the 4th dot-separated segment, so
    # they must not contain '.', and they must not contain path separators.
    for ch in (".", "/", "\\", "\0"):
        if ch in name:
            raise ValueError(f"Invalid character {ch!r} in branch name: {name!r}")
    if name in _RESERVED_BRANCH_NAMES:
        raise ValueError(
            f"Reserved branch name: {name!r} (collides with merge-sidecar grammar)"
        )


def _dt_to_ns(dt: datetime) -> int:
    """Convert a datetime to nanoseconds since the Unix epoch."""
    return int(dt.timestamp() * 1_000_000_000)


def _best_effort_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def _read_sidecar_hash(path: Path) -> str | None:
    """Read a ``.merge`` sidecar's content_hash, validating shape.

    Returns the 64-char hex string, or ``None`` if the file is missing,
    malformed, or has the wrong length."""
    try:
        text = path.read_text().strip()
    except OSError:
        return None
    if len(text) != HASH_LEN:
        return None
    try:
        int(text, 16)
    except ValueError:
        return None
    return text
