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

* **Minimal branching scaffold.** A ``branches`` table tracks branch metadata;
  every revision records its ``branch``; ``put / latest / history / get / verify``
  accept an optional ``branch=`` argument (default ``"main"``). ``"main"`` is
  seeded automatically and behaves byte-for-byte like the upstream store.

* **Optimistic concurrency.** ``put`` accepts an optional
  ``expected_prev_hash``; if the actual tip has moved, ``ConcurrencyConflict``
  is raised instead of silently retrying.

What is **not** here yet (deferred to follow-up):

* ``delete_branch / merge / diff`` operations, branch metadata on the
  filesystem (``data/__branches__/``), multi-parent merge revisions and their
  sidecars, fall-through reads to a parent branch.
* The ``IVersionedStorePort`` (lives in naas-abi-core, not in this library).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .revision import DEFAULT_BRANCH, HASH_LEN, Revision


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


class Store:
    """Append-only versioned blob store with branches.

    Layout on disk::

        {root}/
            index.db                                  ← rebuildable SQLite index
            data/
                {uid}/
                    {ts_ns:020d}.{prev_hash}.{content_hash}            ← main
                    {ts_ns:020d}.{prev_hash}.{content_hash}.{branch}   ← other

    The filesystem is the source of truth for revisions. The SQLite index can
    be nuked and rebuilt from the filesystem at any time via ``rebuild_index``.

    Branch metadata (parent, fork timestamp) currently lives in SQLite only;
    a follow-up will mirror it onto the filesystem under ``data/__branches__/``
    so ``rebuild_index`` can fully reconstruct branch identities. Until then,
    ``rebuild_index`` reconstructs the *set* of branches (from filenames) but
    parent / fork-timestamp metadata is recreated as ``("main", 0)`` for
    discovered branches that aren't already in the index.
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
                """
            )

    def _seed_main_branch(self) -> None:
        with self._db_lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO branches(name, parent, fork_ts_ns, created_at) "
                "VALUES (?, NULL, 0, ?)",
                (DEFAULT_BRANCH, time.time_ns()),
            )

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
        """Register a branch. No data is copied; tips fall through at read time
        (fall-through reads are deferred to the follow-up; for now reads only
        return revisions explicitly written on the requested branch).

        Parent must exist. Branch name must be valid (alphanumeric + ``-``/``_``,
        non-empty, no path separators, no ``.``).
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
        """Return the latest ``Revision`` for ``uid`` on ``branch`` at time
        ``at``, or ``None``."""
        _validate_uid(uid)
        _validate_branch(branch)
        if at is None:
            with self._db_lock:
                row = self._conn.execute(
                    "SELECT ts_ns, prev_hash, content_hash FROM revisions "
                    "WHERE branch = ? AND uid = ? ORDER BY ts_ns DESC LIMIT 1",
                    (branch, uid),
                ).fetchone()
        else:
            ts_limit = _dt_to_ns(at)
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
        """Internal hot-path: latest tip on a branch, validation skipped."""
        with self._db_lock:
            row = self._conn.execute(
                "SELECT ts_ns, prev_hash, content_hash FROM revisions "
                "WHERE branch = ? AND uid = ? ORDER BY ts_ns DESC LIMIT 1",
                (branch, uid),
            ).fetchone()
        if row is None:
            return None
        return self._build_revision(uid, *row, branch=branch)

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
        """Yield every uid that has at least one revision on ``branch``."""
        _validate_branch(branch)
        with self._db_lock:
            rows = self._conn.execute(
                "SELECT DISTINCT uid FROM revisions WHERE branch = ?", (branch,)
            ).fetchall()
        for (uid,) in rows:
            yield uid

    def uids_at(
        self,
        at: datetime | None = None,
        *,
        branch: str = DEFAULT_BRANCH,
    ) -> Iterator[tuple[str, Revision]]:
        """Yield ``(uid, latest_revision)`` for every uid on ``branch`` that
        has a revision at or before ``at``."""
        _validate_branch(branch)
        if at is None:
            with self._db_lock:
                rows = self._conn.execute(
                    """
                    SELECT uid, ts_ns, prev_hash, content_hash
                    FROM revisions
                    WHERE branch = ?
                      AND (uid, ts_ns) IN (
                        SELECT uid, MAX(ts_ns) FROM revisions
                        WHERE branch = ? GROUP BY uid
                      )
                    """,
                    (branch, branch),
                ).fetchall()
        else:
            ts_limit = _dt_to_ns(at)
            with self._db_lock:
                rows = self._conn.execute(
                    """
                    SELECT uid, ts_ns, prev_hash, content_hash
                    FROM revisions
                    WHERE branch = ?
                      AND (uid, ts_ns) IN (
                        SELECT uid, MAX(ts_ns) FROM revisions
                        WHERE branch = ? AND ts_ns <= ? GROUP BY uid
                      )
                    """,
                    (branch, branch, ts_limit),
                ).fetchall()
        for uid, ts_ns, prev_hash, content_hash in rows:
            yield uid, self._build_revision(
                uid, ts_ns, prev_hash, content_hash, branch=branch
            )

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
        silently. Branch metadata not already in ``branches`` is recreated as
        ``parent='main', fork_ts_ns=0`` for any branch discovered in
        filenames (the spec follow-up will store branch metadata on disk so
        parent / fork timestamps are also rebuildable).
        """
        with self._db_lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute("DELETE FROM revisions")
                discovered_branches: set[str] = {DEFAULT_BRANCH}
                # (branch, uid, prev_hash)
                seen_keys: set[tuple[str, str, str]] = set()

                if self.data_dir.exists():
                    for uid_dir in self.data_dir.iterdir():
                        if not uid_dir.is_dir():
                            continue
                        uid = uid_dir.name
                        revs: list[Revision] = []
                        for f in uid_dir.iterdir():
                            if not f.is_file():
                                continue
                            if f.name.endswith(".tmp"):
                                _best_effort_unlink(f)
                                continue
                            try:
                                revs.append(
                                    Revision.parse_filename(uid, f.name, uid_dir)
                                )
                            except ValueError:
                                continue
                        revs.sort(key=lambda r: r.ts_ns)
                        for rev in revs:
                            discovered_branches.add(rev.branch)
                            key = (rev.branch, rev.uid, rev.prev_hash)
                            if key in seen_keys:
                                # Two files share (branch, uid, prev_hash).
                                # Keep the earliest (already inserted), drop
                                # the rest.
                                _best_effort_unlink(rev.path)
                                continue
                            seen_keys.add(key)
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

                # Re-seed any branch we saw on disk that isn't in `branches`.
                now_ns = time.time_ns()
                for b in discovered_branches:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO branches"
                        "(name, parent, fork_ts_ns, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (
                            b,
                            None if b == DEFAULT_BRANCH else DEFAULT_BRANCH,
                            0,
                            now_ns,
                        ),
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


def _validate_uid(uid: str) -> None:
    if not isinstance(uid, str) or not uid:
        raise ValueError("uid must be a non-empty string")
    if "/" in uid or "\\" in uid or "\0" in uid or uid in (".", ".."):
        raise ValueError(f"Invalid uid: {uid!r}")


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


def _dt_to_ns(dt: datetime) -> int:
    """Convert a datetime to nanoseconds since the Unix epoch."""
    return int(dt.timestamp() * 1_000_000_000)


def _best_effort_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
