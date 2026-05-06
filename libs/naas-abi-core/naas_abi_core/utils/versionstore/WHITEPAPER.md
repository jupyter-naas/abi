# versionstore — An Append-Only, Content-Addressed Versioned Blob Store

> *Filesystem is truth. Everything else is a rebuildable view.*

## 1. Motivation

Many systems need to answer one deceptively simple question:

> *What was the state of entity `X` at time `T`?*

This comes up in ontologies (axiom revisions), configuration management (what was
config `foo` yesterday?), audit logs (what did record `R` look like before the
change?), event-sourced applications, versioned documents, and compliance
workflows. Existing tools either solve a narrower problem (Git, focused on
source code), a wider one (Datomic, XTDB — full databases), or one tilted toward
a specific data model (RDF triple stores with history plugins).

`versionstore` is the smallest honest primitive that answers the question
above, for arbitrary byte payloads, with cryptographic integrity and full
rebuildability.

## 2. Design Principles

The design follows five principles, in priority order. When they conflict, the
earlier one wins.

### 2.1 Filesystem is truth

The canonical state of the store lives in plain files on disk. Every other
component — the SQLite index, any downstream projection (RDF, JSON, full-text
search) — is derived data that can be nuked and rebuilt from the filesystem.

This has three practical consequences:

- **Portability.** The data directory is self-describing. `rsync`, `tar`,
  `git`, or `cp -r` is enough to replicate or back up the whole store.
- **Durability.** If the index corrupts or the query engine dies, no data is
  lost. `rebuild_index()` is a pure function of the filesystem.
- **Inspectability.** `ls data/{uid}/` is an audit trail. `sha256sum
  data/{uid}/*.ttl` verifies integrity without running any software.

### 2.2 Append-only, immutable

A revision, once written, is never modified or deleted. Updates are new
revisions. This is what makes the store a trustworthy log and what makes
reasoning about concurrency and recovery tractable.

The store does not model deletion. An "empty" revision (zero-byte payload) is
a legitimate state, not a tombstone. Semantic deletion — if needed at all — is
a consumer's concern, expressed through whatever rule it imposes on empty
revisions (e.g. "hide from default view").

An escape hatch `Registry.drop(namespace)` exists for legal erasure (GDPR),
but it is explicitly not part of normal operation.

### 2.3 Content-addressed, Merkle-chained

Each revision's filename encodes three facts:

```
{ts_ns:020d}.{prev_hash}.{content_hash}
```

- **`ts_ns`** — nanosecond timestamp, zero-padded so lexical sort equals
  chronological sort.
- **`prev_hash`** — SHA-256 of the previous revision's payload (or the
  `GENESIS` sentinel `"0" * 64` for the first revision).
- **`content_hash`** — SHA-256 of this revision's payload.

The filename *is* the Merkle metadata. Tampering with any revision's bytes
causes its content hash to mismatch its filename. Deleting a middle revision
breaks the `prev_hash` chain of the next one. Both are detectable without any
external index, purely from the filesystem.

### 2.4 Payload-agnostic

The store treats payloads as opaque `bytes`. It does not parse, validate, or
index their contents. Interpretation is the consumer's job.

This is what keeps the core small (~150 LOC) and broadly useful. The same
store can back an RDF triple store, a document database, a configuration
service, or a binary blob archive — with no changes to the storage layer.

### 2.5 UIDs are opaque

Keys are opaque strings. UUIDs are strongly recommended (and `uuid7()` is
provided) because:

- They are filesystem-safe everywhere.
- They are collision-free across distributed writers with no coordination.
- They carry no business meaning that could become stale.
- They produce uniformly distributed directory prefixes for sharding.

Consumers that need to look up by a meaningful key (IRI, email, title)
maintain their own `key → uid` mapping. The store does not participate in
that mapping and does not need to.

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Consumers (RDF view, JSON view, FTS view, …)               │
│    Each keeps its own business-key → uid mapping.           │
│    Each is a rebuildable projection over the store.         │
├─────────────────────────────────────────────────────────────┤
│  versionstore.Store                                         │
│    put(uid, bytes) → Revision | None   (None = idempotent)  │
│    get(uid, at=T)  → bytes  | None                          │
│    latest / history / uids / uids_at / verify               │
│    rebuild_index                                            │
├─────────────────────────────────────────────────────────────┤
│  SQLite index (rebuildable)        Filesystem (truth)       │
│    revisions(uid, ts_ns,             data/{uid}/            │
│              prev_hash,                 {ts}.{prev}.{hash}  │
│              content_hash)                                  │
│    WAL mode, BEGIN IMMEDIATE       Atomic .tmp + rename     │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 On-disk layout

```
{root}/
    index.db                                 ← SQLite (rebuildable)
    data/
        {uid_1}/
            00000001745491200000000000.{GENESIS}.{hash_a}
            00000001745491500123000000.{hash_a}.{hash_b}
            00000001745491800987000000.{hash_b}.{hash_c}
        {uid_2}/
            00000001745491300555000000.{GENESIS}.{hash_d}
```

Each `{uid}/` directory is an independent append-only log. Directory
presence answers "has this uid ever been written?"; the latest file answers
"what is its current state?".

### 3.1.1 Durability model

The store offers two durability modes, selected at construction time:

- **`durability="full"` (default).** When `put` returns success, the
  revision is on non-volatile storage. On Linux/Windows/BSD this is what
  `os.fsync` already guarantees. On Apple platforms, regular `fsync(fd)`
  flushes only to the drive controller's cache — a power loss between
  `fsync` returning and the physical write loses the data. Full mode
  closes that gap by using `fcntl(fd, F_FULLFSYNC)` for file syncs and
  `PRAGMA fullfsync=ON` + `PRAGMA synchronous=FULL` for SQLite. The cost
  is real (10–100× per fsync on macOS) but is the price of the durability
  claim being true.
- **`durability="fast"`.** Uses the platform default `fsync`. Identical
  to `"full"` on non-Apple platforms; on Apple it surfaces the cache-only
  behavior described above. Use only when you accept that recently
  acknowledged writes can be lost on a power-loss event — typically in
  development, tests, or for ephemeral data.

The integrity model in §4 is unaffected by the choice: in both modes the
filenames, content hashes, and Merkle chain are identical. What differs
is what "I just acked this write" means in the face of a crash.

### 3.2 Write protocol

```
BEGIN IMMEDIATE                              (SQLite write lock)
    latest       ← SELECT latest revision for uid
    if latest.hash == sha256(payload):       (idempotent no-op)
        ROLLBACK; return None
    prev_hash    ← latest.hash or GENESIS
    ts_ns        ← max(time.time_ns(), latest.ts_ns + 1)
    filename     ← f"{ts_ns:020d}.{prev_hash}.{content_hash}"

    write payload to {filename}.tmp
    fsync(file)                              (or F_FULLFSYNC under "full" on Apple)
    rename {filename}.tmp → {filename}       (atomic on POSIX)
    fsync(dir)                               (best-effort, same mode as above)

    INSERT into revisions(...)
COMMIT
```

Failure modes:

- **Crash before rename:** orphan `.tmp` remains; no final file; no index row.
  `rebuild_index()` deletes the orphan.
- **Crash after rename, before COMMIT:** final file exists, no index row.
  `rebuild_index()` reconstructs the row from the filename.
- **Crash after COMMIT:** consistent state. Nothing to recover.

At no point can a file at its final name contain partial bytes, because the
rename is atomic and the bytes are fsynced before the rename.

### 3.3 Read protocol

The common query — "what is uid `U` at time `T`?" — is trivially fast:

```
SELECT ts_ns, prev_hash, content_hash
FROM revisions
WHERE uid = ? AND ts_ns <= ?
ORDER BY ts_ns DESC LIMIT 1
```

One indexed lookup, one file read. Sub-millisecond on warm cache.

This is the 99% query. It does not touch any RDF engine, query planner, or
projection layer. The store itself answers it.

### 3.4 Rebuild protocol

```
BEGIN IMMEDIATE
    DELETE FROM revisions
    DELETE FROM merges
    for each uid_dir in data/ (skipping data/__branches__/):
        for each file in uid_dir:
            if file ends with .tmp:    delete (orphan)
            elif file ends with .merge: stash as candidate sidecar
            else: parse filename → INSERT revision
        for each accepted revision with a paired sidecar:
            INSERT into merges(branch, uid, ts_ns, other_parent)
        delete any unpaired sidecars (orphans)
    DELETE FROM branches WHERE name != 'main'
    for each branch sidecar in data/__branches__/:
        INSERT OR REPLACE into branches (parent, fork_ts_ns, created_at)
    for each branch discovered in filenames but not in sidecars:
        INSERT with parent='main', fork_ts_ns=0   (legacy fallback)
COMMIT
```

The index is defined entirely by what is on disk. Three artifact classes
participate:

1. **Revision files** (`{ts}.{prev}.{content}[.{branch}]`) — primary state.
2. **Merge sidecars** (`{revision_filename}.merge`, 64-char hex content) —
   second-parent pointer for multi-parent revisions.
3. **Branch sidecars** (`data/__branches__/{name}.json`) — branch DAG identity.

If a file was deleted, its row disappears. If a row was orphaned (e.g. by
external index corruption), it is recreated from the filename. If a branch
sidecar is missing for a branch discovered in revision filenames, the
branch is reseeded with `parent='main', fork_ts_ns=0` — preserving
backward compatibility with stores written before the sidecar grammar
shipped.

### 3.5 The branching DAG

A branch is a named, mutable pointer scoped to a `Store`. Branches form a
DAG rooted at `main`: each non-root branch records its `parent`, the
nanosecond timestamp at which it was forked (`fork_ts_ns`), and its
creation time (`created_at`). The DAG is encoded twice — authoritatively
on disk under `data/__branches__/{name}.json`, and as a cache in the
`branches` SQLite table — so total index loss is recoverable.

Three operations exercise the DAG:

#### 3.5.1 Fall-through reads

A read on branch `B` for uid `U`:

```
function resolve(uid, branch, ts_limit):
    own = latest revision of (branch, uid) with ts_ns <= ts_limit
    if own exists: return own
    if branch has no parent: return None
    return resolve(uid, parent(branch), min(ts_limit, fork_ts_ns(branch)))
```

The recursive cap on `ts_limit` is the key invariant: a child branch sees
its parent's state *as of the fork moment*, never any later writes the
parent made after the branch existed. This makes branches durable
snapshots without copying any bytes.

The write path stays per-branch: own chains start at `GENESIS` and never
chain off an inherited tip. This keeps `verify` per-branch and lets
branches be deleted without affecting any other branch's chain validity.

#### 3.5.2 Merge — multi-parent revisions

`Store.merge(source, target, *, resolver, strategy)` reconciles two
branches per uid, using the target's view at `source.fork_ts_ns` as the
base:

| `source_tip` | `target_tip` | `base` | Outcome |
|--------------|--------------|--------|---------|
| `=` target   | `=` source   | any    | `no_op` |
| changed      | unchanged    | base   | `fast_forwarded` (apply source bytes on target) |
| unchanged    | changed      | base   | `no_op` (target's work wins) |
| changed      | changed      | base   | `three_way_merged` (resolver) or `conflicts` |
| present      | absent       | absent | `fast_forwarded` (uid added on source) |

Each `fast_forwarded` / `three_way_merged` uid produces one new revision
on `target` *plus* a `.merge` sidecar containing `source_tip.content_hash`
(the second parent). The new revision's `prev_hash` is the prior
own-target tip (its first parent), so the per-branch chain stays linear
and `verify` requires no special case for merges.

The `merges` SQLite table is a (branch, uid, ts_ns) → other_parent index,
rebuildable from the on-disk sidecars.

`MergeStrategy.FAST_FORWARD` raises `MergeConflict` on the first uid that
needs three-way reconciliation (all-or-nothing semantics). `THREE_WAY`
collects conflicts (resolver returned `None`) and raises `MergeConflict`
at the end with the partial `MergeResult` attached, so callers can
inspect what was applied before the conflict surfaced. Merges are
non-atomic across uids by design — each uid's write is independently
durable, and re-running `merge` after a partial run picks up where it
left off (already-applied uids fall into `no_op`).

V1 limitation: `merge` requires `source.parent == target`. Transitive
merges (a grandchild back to a grandparent) need a real common-ancestor
walk, deferred to a follow-up issue.

#### 3.5.3 `delete_branch` and reachability

`delete_branch(name)` removes the branch's own revision files, their
`.merge` sidecars, the metadata sidecar, and the corresponding
`revisions` / `merges` / `branches` rows. It refuses `main` and refuses
when any branch's `parent` points at the target — the caller must
delete or re-parent children first.

This works because fall-through walks *up* the DAG (child → parent),
never down, so removing a leaf branch can never invalidate an ancestor's
reads. After `delete_branch` + `rebuild_index`, no orphaned references
remain — that is the reachability-GC contract.

## 4. Integrity Model

The filesystem alone is sufficient to:

1. **Detect content tampering.** Rehash `data/{uid}/{filename}`; compare to the
   `content_hash` segment of the filename.
2. **Detect revision deletion.** Walk a uid's files sorted by timestamp;
   verify each file's `prev_hash` equals the previous file's `content_hash`.
3. **Detect revision insertion/reordering.** Same Merkle chain check.
4. **Detect rename-style attacks.** A file's `content_hash` segment must
   match `sha256(file_bytes)`. Renaming a file into a different position or
   uid changes nothing about the Merkle chain because the hash is intrinsic.

`Store.verify(uid)` performs the full chain walk in one pass. It does not
consult the SQLite index; it reads from disk only.

### 4.1 Multi-parent revisions

A merge revision is a normal revision file (its `content_hash` is the
SHA-256 of its bytes; its `prev_hash` is the prior own-branch tip's
`content_hash`) accompanied by a `.merge` sidecar containing the second
parent's `content_hash`. The single-line per-branch chain is therefore
unchanged — `verify(uid, branch=B)` walks `B`'s revisions chronologically
and validates `prev_hash` equals the prior revision's `content_hash`,
exactly as for non-merge revisions.

The second parent is informational, not load-bearing for integrity: it
records which cross-branch state was incorporated, useful for tooling
(merge graphs, blame) and for reconstructing the DAG. A missing or
malformed sidecar does not invalidate the revision; it only loses the
cross-branch ancestry hint, which `rebuild_index` cleans up by deleting
the sidecar.

The threat model this covers is **local integrity**. It does not cover
adversaries who can rewrite the entire `data/` directory, including the
GENESIS-rooted chain, in a coordinated way. For that, pair the store with
an external notarization mechanism (signed periodic tip hashes, transparency
log, blockchain timestamp, etc.). The store's design accommodates this
trivially — the tip hash is just the latest file's `content_hash`.

## 5. Concurrency

### 5.1 Single host, multiple writers

SQLite WAL mode permits many concurrent readers and one writer at a time.
Writes acquire `BEGIN IMMEDIATE` around the read-latest-then-insert sequence,
so two processes writing to the same uid cannot both read the same `latest`
and both try to insert with the same `prev_hash`. The second writer waits
(respecting `busy_timeout`) and sees the first writer's revision as its
predecessor.

This serializes all writes across the whole store. For workloads where that
contention becomes visible, the SQLite schema could be extended with a
`UNIQUE(uid, prev_hash)` constraint and per-uid retry logic, trading
simplicity for per-uid concurrency. The default is "one writer at a time"
because that is correct and sufficient for most real workloads.

### 5.2 Multiple hosts

Not supported. The SQLite index is local; the filesystem lock semantics
across network filesystems are unreliable. A multi-host deployment needs a
different coordination layer (shared SQL database, Raft, etc.), at which
point the design trade-offs change significantly. The store deliberately
does not try to be that system.

## 6. Consumers and Projections

The store's contract ends at `bytes in, bytes out, versioned by time`.
Consumers layer meaning on top. The canonical consumer in this project is an
RDF view over the store; other consumers are possible.

### 6.1 The materialized-view pattern

For consumers that want to answer rich queries (e.g., SPARQL across many
subjects), the recommended pattern is **on-demand materialization**:

```
def sparql(self, query: str, at: datetime | None = None):
    with fresh_oxigraph() as g:
        for uid, rev in self.store.uids_at(at):
            g.load(rev.read())
        return g.query(query)
```

The query engine is an ephemeral tool, not a persistent component. It is
instantiated to answer a question and discarded (or cached by
`(query, at)` if hot). This scales effortlessly: the store holds millions of
revisions on disk without paying any cost for a "live" index, and
materialization loads only what a specific query needs.

For the 99% query — "state of uid `U` at time `T`" — no materialization is
needed. The store's `get(uid, at=T)` is a direct key-value lookup.

### 6.2 Consumers keep their own indexes

Consumers that need to look up by a business key maintain their own mapping,
rebuildable from the store. For an RDF view, that's an `iri → uid` table; for
a document view, a `slug → uid` table; for an email archive, a
`message-id → uid` table. These indexes are not part of the store — they are
consumer state.

When a consumer rebuilds, it walks the store's revisions (`uids_at()` or
`history(uid)` per uid), parses payloads according to its own format, and
repopulates its mapping. The store does not know or care that this happens.

## 7. Namespacing

Namespaces are not a first-class store concept. They are simply
multiple `Store` instances rooted at different paths:

```python
users   = Store("data/users")
configs = Store("data/configs")
```

Each is isolated: separate SQLite, separate files, separate concurrency
domain. The optional `StoreRegistry` is a thin wrapper for managing many of
them under one parent directory.

Two namespaces may share the same uid string; they are unrelated entities.
If a consumer wants globally unique uids across namespaces, it uses UUIDs and
tracks `(namespace, uid)` tuples itself.

## 8. What the store does not do

Deliberate exclusions, each justified by the principle of keeping the core
small and generic:

- **Access control.** A consumer concern.
- **Schema validation.** Payloads are bytes; the store cannot and should not
  parse them.
- **Replication or multi-host writes.** A different kind of system.
- **Content queries.** Queries are by `uid` and time only; anything else is
  a consumer-built index.
- **Garbage collection or compaction.** Append-only forever. If retention is
  needed, a policy layer wraps the store.
- **Tombstones or delete semantics.** The store logs bytes; "deletion" is a
  view concern that consumers express however they like.
- **Encryption at rest.** Delegated to the filesystem or a dm-crypt/LUKS/APFS
  layer beneath. Encrypting at the store layer would defeat
  content-addressability.

Each of these is a legitimate feature of *some* systems. None of them belong
in the store, because including them would couple it to specific use cases
and break the "one small primitive, many consumers" factoring.

## 9. Scaling Characteristics

| Dimension           | Cost                                  | Notes                                   |
|---------------------|---------------------------------------|-----------------------------------------|
| `put(uid, bytes)`   | O(1) disk + one SQLite insert         | Bounded by fsync latency.               |
| `get(uid, at=T)`    | O(log n) SQLite lookup + one read     | n = revisions for that uid.             |
| `history(uid)`      | O(n) SQLite scan                      | n = revisions for that uid.             |
| `uids_at(T)`        | O(U) SQLite scan                      | U = total uids in the store.            |
| `verify(uid)`       | O(n) disk reads + hashes              | n = revisions for that uid.             |
| `rebuild_index()`   | O(N) disk walk                        | N = total revisions across all uids.    |

Practical ceilings on reasonable hardware:

- **Revisions per uid:** unlimited in principle; directory listings and
  SQLite lookups remain fast into the millions.
- **Total uids:** SQLite comfortably handles 10M+ rows on the `revisions`
  table. The main constraint is filesystem behavior on directories with many
  entries. For `> 100k` uids, shard the data directory with a prefix scheme
  (`data/{uid[:2]}/{uid}/...`).
- **Payload size:** bounded by filesystem and available disk. The store
  makes no assumption about payload size. Very large payloads should be
  content-addressed separately (e.g., payloads holding hash references to
  a separate blob store) — otherwise every revision copies the full bytes.

## 10. Relationship to Existing Systems

The design is not novel in any individual piece; most components have prior
art. Its value is the specific combination.

- **Perkeep** (née Camlistore) — the closest overall match, with
  "permanodes" playing the role of uids and "claims" playing the role of
  revisions. Perkeep is heavier (signing, networking, search, schema blobs);
  `versionstore` is the 150-line essence.
- **XTDB / Datomic** — share the bitemporal/time-travel query model, but
  are full databases with schema and rich query. `versionstore` has no
  schema and no query beyond `(uid, time)`.
- **Dolt / Noms** — content-addressed, versioned, Git-inspired data stores.
  Tuned for tabular/schema data; `versionstore` is tuned for opaque blobs.
- **Git + git-annex** — same primitive (content-addressed, Merkle-chained,
  immutable), but Git's access patterns optimize for source-code-shaped
  data (small related files, diff-heavy reads), not "random uid lookup at
  time T".
- **Quit Store / R43ples** — RDF-specific versioning. `versionstore` is
  one layer below: it can back a quit-store-like consumer, among others.
- **Event-sourcing systems (EventStore, Kafka + ksqlDB)** — the log + view
  pattern is the same. `versionstore`'s log is whole-entity snapshots, not
  event deltas, which is simpler but less bandwidth-efficient for
  high-frequency writers.

Where `versionstore` is distinctive:

1. **Filesystem, not a pack format, as truth.** Every revision is a
   separately-inspectable file.
2. **Filename-encoded Merkle metadata.** No sidecar files, no chain file,
   no database required to verify integrity.
3. **SQLite as a pure index.** Rebuildable in seconds from the filesystem;
   not a system of record.
4. **Payload- and consumer-agnostic core.** RDF, JSON, binary — all the
   same from the store's perspective.
5. **~150 LOC of runtime code, stdlib only.** No dependencies to audit, vendor,
   or version.

## 11. Future scaling: group commit

The single dominant cost in the write path (§3.2) is `fsync`. On local SSD,
`fsync(file)` and `fsync(dir)` are each ~1–10 ms — orders of magnitude more
than every other step combined (hashing, SQLite insert, rename). Sequential
writes are bound by this: 1000 puts ≈ 10 seconds of fsync wait, regardless of
how fast the rest of the code runs.

The classical answer is **group commit**: a single fsync durably persists
*every* write that landed in the same file or directory since the previous
fsync. So if N writers each have a `.tmp` ready, one fsync can persist all N
of them. The per-write fsync cost falls from O(1) to O(1/N).

### 11.1 Mechanism

Writers opt into a small "commit group" with a bounded delay window (e.g.
2–10 ms) and a bounded size (e.g. 64 writes). When either bound is reached,
one designated leader thread runs:

1. A single `fsync` over all `.tmp` files in the group.
2. The atomic `rename` of each `.tmp` to its final filename, in chain order
   per `(uid, branch)` so prev_hash chains stay valid on crash.
3. A single `fsync` of each touched `uid_dir`.
4. The corresponding INSERTs into the index, batched in one transaction.
5. A wake of every writer in the group, each receiving its own `Revision`.

Writers that arrive while a group is committing join the next group. The
window is the only added latency; the throughput floor rises linearly with
group size.

This is the same pattern SQLite uses internally for its own commits and that
PostgreSQL exposes as `commit_delay` / `commit_siblings`. It is a pure
amortization of fsync; no other guarantees are weakened.

### 11.2 Compatibility with the design principles

Each principle from §2 is examined in turn.

- **§2.1 Filesystem is truth.** Unchanged. Group commit only changes *when*
  fsync happens; the bytes that land on disk and the filenames they land
  under are identical to the non-grouped path. `rebuild_index` is unaffected.
- **§2.2 Append-only, immutable.** Unchanged. Group commit never mutates an
  existing revision; it batches the *durability* of new ones.
- **§2.3 Content-addressed, Merkle-chained.** Unchanged. `prev_hash` and
  `content_hash` are computed exactly as today. The chain semantics are
  invariant.
- **§2.4 Payload-agnostic.** Unchanged. The store still treats payloads as
  opaque bytes.
- **§2.5 UIDs opaque.** Unchanged.

The single shift is in the failure model (§3.2), spelled out below.

### 11.3 Updated failure modes

Without group commit, every successful `put` was individually durable before
returning. With group commit, **a `put` returns only after its group's fsync
has completed**, so durability is preserved at the moment of return. The
only change is what a crash mid-batch leaves behind:

- **Crash before the group's fsync:** every member's `.tmp` may exist; no
  finals; no INSERTs. `rebuild_index` deletes the orphan `.tmp` files. Same
  outcome as today's "crash before rename." No writer received a success
  acknowledgement, so no claim of durability was violated.
- **Crash after fsync, partway through the rename loop:** a *prefix* of the
  group's writes are renamed to their final names; the rest are still
  `.tmp`. The renamed files are valid revisions on disk — they simply lack
  their index rows. `rebuild_index` reconstructs those rows from the
  filenames; the un-renamed `.tmp`s are cleaned up. Writers whose files made
  it past the rename observe the same outcome as today's "crash after
  rename, before COMMIT."
- **Crash during the batched INSERT, after all renames succeeded:** the
  finals exist; no INSERTs. `rebuild_index` reconstructs the index from the
  filesystem. Identical to today.

In all cases, the per-file invariants from §3.2 hold: a file at its final
name contains complete, fsynced bytes whose `content_hash` matches its
filename. The Merkle chain (§4) remains verifiable end-to-end.

The one new operational rule is that **the leader thread acknowledges
writers only after the group's fsync has completed**. That preserves the
contract that `put` returning success implies durable.

### 11.4 Cost and tuning

The latency–throughput trade-off is a single knob. Some realistic shapes:

| Window | Group size (typical) | Per-write fsync cost | Added latency |
|--------|----------------------|----------------------|---------------|
| 0 ms (off, today) | 1 | ~5 ms | 0 ms |
| 2 ms              | 5–20 | ~0.3–1 ms | up to 2 ms |
| 10 ms             | 30–100 | ~0.05–0.3 ms | up to 10 ms |

For workloads with **many concurrent writers** — exactly the situation
created by per-(branch, uid) concurrency — group commit converts the
per-write fsync cost from a hard ceiling into a knob. For single-writer
workloads it's a pure latency penalty; the knob should default to off.

A reasonable default when enabled: a 2 ms window with a 64-write cap. In
the consumer's view, latency stays sub-frame-rate; throughput on contended
workloads rises by 1–2 orders of magnitude.

### 11.5 Implementation status

Group commit is **implemented in the ABI-vendored copy** of versionstore
(see ``libs/naas-abi-core/naas_abi_core/utils/versionstore/``). It is
**opt-in via a constructor argument** (``commit_window_ms``); the default
remains ``0.0`` so deployments that don't enable it pay nothing and behave
byte-for-byte like the pre-group-commit code path. The implementation
follows the leader-follower mechanism described above:

- A first-arriving writer with no open group becomes the leader. Followers
  arriving within the window join the open group.
- The leader sleeps on a condition variable until either the window
  expires or the group reaches ``commit_max_size``. Followers signal the
  condvar on join so the leader wakes early when the cap is hit.
- ``_commit_batch`` fsyncs each tmp, renames in chronological order
  (so partial-rename crashes leave a valid prefix), deduplicates
  ``uid_dir`` fsyncs, and runs all index inserts in a single transaction
  with per-row ``SAVEPOINT`` so a single ``UNIQUE`` conflict only fails
  that member rather than the batch.
- Two diagnostic counters (``_batch_count``, ``_batched_writes``) are
  exposed on the ``Store`` for tests and observability.

It composes cleanly with the per-uid and per-(branch, uid) concurrency
paths: the retry loop, the ``UNIQUE`` constraint, and the in-process
per-(branch, uid) lock all stay valid. Group commit slots into the
file-write path; nothing else changes.

The upstream library should track this change once the model has been
exercised in production — the vendored implementation is the reference.

## 12. Summary

`versionstore` answers the question "what was entity `X` at time `T`?"
with:

- a plain-file canonical log,
- Merkle-verifiable content-addressed filenames,
- a rebuildable SQLite index for fast lookups,
- an ACID write path,
- a generic byte-payload contract,
- and nothing else.

Its scope is deliberately small. Query, schema, access control,
replication, and semantic interpretation are left to consumers. The design
trades generality in the storage layer for composability across many
consumer domains, and it trades feature richness for the property that a
determined engineer can understand the entire system — and rebuild it from
the filesystem — in an afternoon.
