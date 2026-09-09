# Portable document service

Status: Proposed

Date: 2026-09-09

## Context

[Issue #1257](https://github.com/jupyter-naas/abi/issues/1257) calls for mutable
module state that runs locally without PostgreSQL and uses PostgreSQL in deployed
environments. Dataset snapshots and non-enumerable key-value storage do not meet
that contract. Returning infrastructure connections would couple modules to a
deployment backend.

## Decision

Introduce `DocumentPort`, `DocumentService`, and `DocumentFactory`, following the
core's existing service layout and the issue's Python value/spec API. SQLite and
psycopg adapters share SQL-specific code only in their secondary-adapter package.
Modules declare the dependency and receive a service scoped to their complete
module name through `EngineProxy`; their own domain ports remain independent.

Use one documents table and one persisted collection catalog with namespace
columns in a dedicated PostgreSQL schema. Provision them idempotently at adapter
load, using an existing deployment database. Collections require no separate
table or database. The same layout works in a SQLite file. Initialization errors
propagate before modules load. No ORM or new dependency is required.

Resolve the issue's open decisions as follows:

- Return complete documents; omit projection.
- Interpret `contains` as exact array membership only.
- Merge declarations additively. Never drop an omitted index or constraint.
- Use sparse uniqueness, excluding null/missing fields and compound keys with
  any null/missing component. Adding invalid uniqueness fails transactionally.
- Bind all predicates to literal top-level fields, combine them with AND, and
  distinguish missing fields from explicit null. Ranges compare scalar kinds.
- Materialize filter iterables before validation and retain them across pages.
  Canonicalize AND-predicate order for cursor binding. Bound individual pages
  and iteration batches to 1,000 documents (plus one continuation sentinel).
- Use a portable scalar sort order, with numeric casts, UTC dates, binary string
  collation, and ID tie-breakers. Containers tie by kind then ID. Keyset cursors
  bind to the query and retain the anchor values, even if its record is deleted.
- `if_version=None` unconditionally replaces/upserts; 0 creates only; positive
  versions require a match. Deleting/recreating an ID starts a new version
  sequence. Bulk operations provide per-document atomicity and may commit a
  prefix. Version-aware bulk deletion surfaces concurrent changes.
  A supplied delete version must match an existing document, including when
  zero is supplied; zero's create-only interpretation is specific to `put`.

Use reversible tag-key escaping for datetimes/bytes at any nesting depth. Reject
naive datetimes, non-finite floats, integers outside signed 64 bits, and NUL or
invalid UTF-8 strings to keep SQLite and PostgreSQL semantics aligned. Declarations
validate existing values, while undeclared fields remain queryable.
Object key order is unspecified, matching JSONB; lists preserve order. Shared
type ranks and byte sort keys, with paging tests over every value kind, keep
database sorting aligned with cursor continuation values.
PostgreSQL may normalize integral floats to integers. Decode expanded JSONB
integers outside signed 64 bits back to floats, since they can only originate
from valid float inputs. This keeps retrieved documents within the port's value
range and preserves cursor paging for large finite floats.

Use independent SQLite file connections per transaction and retain a serialized
connection for `:memory:`. Access literal fields through a deterministic function
instead of SQLite JSON paths, whose escaping behavior differs across versions.
Build equality expression indexes alongside typed sort/range indexes; exclusions
and array membership may scan. Repair outdated SQLite indexes transactionally
when ensuring a collection. PostgreSQL leases transactions from a bounded pool;
adapter owners release resources with `close()`.
PostgreSQL expression indexes store a fingerprint of their defining SQL in an
adapter-owned index comment. Ensuring a collection transactionally replaces
missing/stale definitions and rolls back on uniqueness failure. Compound
uniqueness deduplicates field permutations while preserving the first index order.

Keep catalog queries and PostgreSQL row locks on every operation for cross-process
declaration/drop correctness. Cache parsed immutable specs per adapter by their
exact catalog JSON, bounded to 128 entries; never cache away the catalog check.

Only engine-created root services may produce namespace-bound handles. Scoped
handles retain service wiring and reject namespace rebinding. Proxies reuse their
scoped handle, retaining access checks and refreshing it when the engine root
changes. The root cannot store data, and standalone factories require an explicit
namespace. Remote root and
scaffold configurations explicitly select the deployment's PostgreSQL database.

Interim reliability defaults are a 5-second SQLite busy timeout, 5-second
PostgreSQL connection timeout, and 30-second PostgreSQL statement timeout. The
PostgreSQL pool has one initial connection, at most ten connections, and a
5-second startup/acquisition timeout; all are configuration options except the
initial size. Read transactions also lock catalog rows, so PostgreSQL deliberately
does not interpret the shared `write=False` flag as SQL read-only mode.
Boot advisory-lock waits are bounded by the same statement timeout. Backend
driver/pool/locking failures become `DocumentStorageError`; causes remain
available and write outcomes can be ambiguous. Incompatible declarations fail
with collection/document context and roll back; migrate data before enabling
those declarations rather than bypassing validation during boot.
There is no automatic write replay, added telemetry, or new inter-domain
authentication mechanism. Module scoping is an application boundary, not
protection against hostile code running in the same process.

Numeric equality, uniqueness, ranges, and cursor boundaries use JSON decimal
values consistently across adapters. SQLite retains decimal text for numeric
comparison through a Decimal collation; it does not round through SQLite REAL.
Integral float equality uses the serialized decimal value rather than Python's
binary-to-integer conversion. Versioned SQLite equality functions trigger index
repair, retaining the legacy function for safe migration/rollback.

PostgreSQL optional range/sort indexes bound their text/bytes key to 256
characters so an optimization hint cannot reject long valid values. Full-value
query and cursor comparisons remain authoritative; string/bytes ordering may
need a separate sort. Numeric/rank index prefixes and GIN equality candidates
remain available. Existing index fingerprints trigger transactional replacement.

## Consequences

Modules can replace adapters through configuration without changing storage
calls. Generic tests run against both databases to verify this contract. SQLite
requires JSON support and version >= 3.38. PostgreSQL credentials need DDL rights
within the service schema; database provisioning and external application
databases remain deployment responsibilities.

Collections remove structural field migrations, not semantic migrations. Modules
must keep an application `_schema` separate from the CAS `version`, centralize
upcasts, and perform resumable version-checked backfills. Index creation can
block writers; index removal/type changes require deliberate migrations. The
collection catalog and document data must be backed up and restored together.

There are no joins, foreign keys, cross-document transactions, or raw SQL escape
hatches. Paging tolerates inserts but does not promise a snapshot under changes
to sort keys. Moving from SQLite to PostgreSQL still requires data migration.

Implementation references: [PostgreSQL JSON operators](https://www.postgresql.org/docs/current/functions-json.html),
[SQLite JSON functions](https://www.sqlite.org/json1.html), and
[psycopg transaction management](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).
