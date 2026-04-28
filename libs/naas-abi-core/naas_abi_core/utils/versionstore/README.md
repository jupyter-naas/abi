# versionstore

An append-only, content-addressed versioned blob store.

> *Filesystem is truth. Everything else is a rebuildable view.*

Vendored from [Dr0p42/versionstore](https://github.com/Dr0p42/versionstore) for use as
the substrate for ABI's branched, versioned services. See `WHITEPAPER.md` for the
design rationale.

## What lives here

- `store.py`            — the `Store` itself (versioned, branched, content-addressed).
- `revision.py`         — the immutable `Revision` record.
- `registry.py`         — `StoreRegistry`: manage many namespaced stores under one root.
- `uuid7.py`            — stdlib-only UUIDv7 generator.
- `*_test.py`           — sibling tests, per ABI's convention.

## Deviations from upstream

This vendored copy adds three scaling improvements (Tier 1 A, B & C from the
ABI branching spec), a cross-platform durability mode, and the minimal
branching scaffold required for B:

0. **Cross-platform durability (`durability="full"`, default).** On Apple
   platforms, ``os.fsync`` only flushes to the drive controller cache, not
   the platter — a power loss between fsync returning and the physical
   write can lose recently-acknowledged writes. Full mode escalates to
   ``fcntl(fd, F_FULLFSYNC)`` and the matching SQLite PRAGMAs
   (``fullfsync=ON``, ``synchronous=FULL``) so the store's claim that "if
   ``put`` returned success, the revision is durable" holds on every
   supported platform. Pass ``durability="fast"`` to opt out for dev/tests.
   On Linux/Windows/BSD ``"full"`` and ``"fast"`` are equivalent (regular
   ``fsync`` already provides true durability there).

1. **Per-uid concurrency (A).** Two writers touching different uids no longer
   serialize through a single `BEGIN IMMEDIATE` lock. The schema enforces
   `UNIQUE(branch, uid, prev_hash)`; on conflict the writer retries against
   the new tip.
2. **Per-(branch, uid) concurrency (B).** Two writers on different branches
   touching the same uid don't conflict either, since `prev_hash` lookups are
   scoped to the branch's tip.
3. **Group commit (C, opt-in).** Pass `commit_window_ms > 0` to `Store(...)`
   to enable batched fsyncs. A leader-follower scheme amortizes file fsync,
   directory fsync, and the SQLite COMMIT across every writer that lands in
   the same window. Defaults to off. See `WHITEPAPER.md §11` for the full
   model and updated failure semantics.
4. **Minimal branching.** A `branches` table tracks branch metadata, every
   revision now records the branch it was written on, and `put / latest /
   history / get` accept an optional `branch=` argument (default `"main"`).
   Existing call sites are unchanged in behavior.

Multi-parent merge revisions, branch fall-through reads, `merge`/`diff`
operations, and the branch sidecar files described in the spec are **not**
included here yet. They land in a follow-up alongside the `IVersionedStorePort`.

### Enabling group commit

```python
from naas_abi_core.utils.versionstore import Store

# Solo commit (default): every put fsyncs individually.
store = Store("data/")

# Group commit: writers within a 2 ms window share one fsync round.
# Recommended for workloads with many concurrent writers.
store = Store("data/", commit_window_ms=2.0, commit_max_size=64)
```

Diagnostic counters `_batch_count` and `_batched_writes` are exposed on the
store for tests and observability. A ratio
`_batched_writes / _batch_count` near 1.0 means you're paying the latency
cost without getting batching benefit (lower the window, or disable). A
high ratio (e.g. 16 in the bundled tests) means fsync is being amortized
across that many writers per round.
