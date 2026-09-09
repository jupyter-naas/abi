# Document Service - AGENTS.md

## Purpose

Portable mutable application state in namespace-bound collections. A document is
the unit of atomicity: no joins, foreign keys, multi-document transactions, raw
SQL, projection, or analytical snapshots. Dataset and key-value services retain
their existing responsibilities.

## Files

| File | Role |
|---|---|
| `DocumentPort.py` | `IDocumentAdapter`, value/spec/result types, validation, exceptions |
| `DocumentService.py` | Namespace-bound API and bulk/paging conveniences |
| `DocumentFactory.py` | SQLite and PostgreSQL composition helpers |
| `adapters/secondary/DocumentSecondaryAdapterSQLite.py` | SQLite connections and transactions |
| `adapters/secondary/DocumentSecondaryAdapterPostgreSQL.py` | psycopg connections, JSONB and boot provisioning |
| `adapters/secondary/document_sql.py` | Shared SQL compilation and storage operations |
| `adapters/secondary/document_codec.py` | Tagged values, shared sort kinds, and SQLite equality/accessor functions |
| `tests/document__secondary_adapter__generic_test.py` | Reusable adapter contract |

## Port

`IDocumentAdapter` is a runtime-checkable protocol with `ensure_collection`,
`drop_collection`, `collections`, `put`, `get`, `delete`, `find`, `count`, and `close`.
Every operation takes an explicit namespace. Every adapter must implement every
method. Exceptions are `CollectionNotFound`, `DocumentNotFound`,
`VersionConflict`, and `UniqueViolation`.

`CollectionSpec` declares optional typed fields and `unique_together`. Undeclared
fields remain storable and queryable. Declared fields can be absent/null; other
values must match their declared type (float fields also accept integers).
Adding declarations validates existing documents. Type changes are rejected.
Declarations merge additively: omitting an existing field, index, or uniqueness
constraint does not remove it. Adding a violated unique constraint rolls back
and raises `UniqueViolation`. Index removal requires explicit maintenance.

Values are strings, signed 64-bit integers, finite floats, booleans, null, aware
datetimes, bytes, lists, and string-keyed dictionaries, recursively. Naive dates,
Decimal, non-finite floats, NUL in strings/keys, and invalid UTF-8 are rejected.
Use bytes for arbitrary binary content. Datetimes normalize to UTC with
microsecond precision. Datetimes/bytes use tagged JSON; user keys beginning with
`$` are escaped so user dictionaries cannot collide with internal tags.
Object key order is unspecified (including nested dictionaries); values and
types are preserved. Encode ordered entries as lists when order matters.

## Service API

Modules declare `DocumentService` in `ModuleDependencies.services`. The engine
loads its configured adapter before module initialization, so connection and
provisioning failures stop loading. `self._engine.services.document` binds the
module's complete dotted name as its namespace. Callers never pass a namespace
on CRUD/query operations. This is module isolation by API convention, not a
security sandbox against hostile Python code with process access. Only the
engine root created through `_for_engine` may bind namespaces; returned handles
reject `_for_namespace` rebinding and retain the root's service wiring.

```python
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.document.DocumentPort import CollectionSpec, FieldSpec
from naas_abi_core.services.document.DocumentService import DocumentService

# On the module class:
dependencies = ModuleDependencies(modules=[], services=[DocumentService])

# During on_initialized(), at the module's composition root:
documents = self._engine.services.document
documents.ensure_collection(
    CollectionSpec(
        name="run_requests",
        fields=(FieldSpec(name="requested_at", type="datetime", indexed=True),),
    )
)
# Inject documents into a secondary adapter implementing the module's own port.
# Module domain code must not import DocumentService.
```

- `put(collection, id, data, if_version=None)` replaces the complete document.
  None is unconditional upsert; 0 is create-only; positive values require the
  current version. New documents start at version 1. Updates increment it and
  preserve `created_at`. Versions reset after deleting and recreating an ID;
  avoid reusing IDs when stale references may still exist.
- `get` raises `DocumentNotFound`. `exists` catches only that exception.
- `delete` is idempotent without a version. With a version, absence or a mismatch
  raises `VersionConflict`.
- `find`, `find_one`, `count`, and `iterate` support AND-combined top-level
  predicates. Field names are literal keys; dots do not select nested paths.
- `eq` is exact structural equality, including array order and all object keys;
  booleans differ from numbers, while numeric 1 equals 1.0. `eq None` matches
  explicit null only. `exists` distinguishes missing from present (including
  null). `ne` and `nin` exclude missing fields. `in`/`nin` take lists.
- `contains` is exact array-element membership, including objects/arrays as
  elements. It does not do string substring or partial-object matching.
- Ranges compare non-null scalars of the same kind. Sorting is ascending by
  default ID, or by `(field, asc|desc)` with ID as a tie-breaker in the same
  direction. Scalar ordering is null/missing, boolean, number, string, datetime,
  bytes. Numbers sort numerically, dates by UTC instant, and bytes by byte value.
  Strings/IDs use binary collation. Arrays then objects follow scalars; containers
  of the same kind tie by ID. No recursive container ordering is promised.
- Cursors include the last sort values and ID, survive deletion of the anchor,
  and are bound to the namespace, collection, filter, and ordering. They are
  opaque continuation tokens, not encrypted credentials. An inserted document
  before the cursor does not shift the next page. Paging is not a snapshot;
  changing sort values during iteration can repeat or omit documents.
- `put_many` and `delete_many` commit per document and stop on an error, leaving
  an already committed prefix. `delete_many` checks each observed version so it
  cannot silently delete a concurrently changed document. `iterate(batch=500)`
  pages internally; `find(limit=100)` returns `Page(items, cursor)`.

Unique constraints are sparse: missing or null fields do not conflict. For a
compound constraint, any missing/null component exempts that document. Constraints
are scoped to a collection and namespace and enforced by database indexes.

## Adapters

SQLite requires >= 3.38 with JSON functions. A file uses WAL, a 5-second busy
timeout, and an independent connection per transaction, so readers do not block
each other or writers; writes use `BEGIN IMMEDIATE`. Independent adapters/processes
can share the file. `:memory:` retains one serialized connection for tests.
Literal field lookup uses a deterministic function, avoiding version-dependent
JSON-path escaping. `indexed=True` creates typed range/sort and exact equality
expression indexes. Equality and `in` can use the equality index; SQLite chooses
plans using its statistics. Exclusions and array `contains` can still scan.
`ensure_collection` transactionally repairs outdated expression indexes even if
the declaration is unchanged; conflicting data raises `UniqueViolation` and
rolls back the repair. Both adapters expose `close()` and reject subsequent use.
An in-flight SQLite file transaction releases its own connection when it ends.
Use the service adapter when
writing the file because expression indexes use its registered SQLite functions.

PostgreSQL uses the existing psycopg pool dependency, leasing a connection and
transaction per operation, and one documents table plus a collection catalog in the configured
schema. A namespace column scopes all statements and partial indexes. A GIN index
accelerates containment candidates; exact equality still checks full values.
`indexed=True` creates expressions matching the typed range/sort expressions.
Collection locks coordinate writes with declaration changes and teardown; CAS
updates/deletes check the version in the modifying statement. Boot DDL is
serialized across processes and runs on every adapter initialization.

The PostgreSQL database must already exist; reuse the deployment database.
Credentials need permission to create/use the configured schema, tables, and
indexes. No new database, ORM, authentication scheme, or additional dependency
is introduced. The pool starts with one connection and grows to at most ten;
startup and acquisition time out after 5 seconds. Defaults: 5-second connection
timeout and 30-second statement timeout (milliseconds in config). PostgreSQL
reads also lock catalog rows; the shared `write` flag only selects SQLite's
locking mode, not PostgreSQL read-only transactions. Failures are surfaced without automatic
replay, including ambiguous commit failures. No retry/circuit-breaker policy or
additional telemetry is introduced.

## Factory and configuration

`DocumentFactory.DocumentServiceSQLite(path, namespace)` and
`DocumentFactory.DocumentServicePostgreSQL(dsn, namespace)` construct standalone
services. Engine configuration defaults to SQLite:

```yaml
services:
  document:
    document_adapter:
      adapter: sqlite
      config:
        path: storage/documents.sqlite
        timeout: 5.0
```

```yaml
services:
  document:
    document_adapter:
      adapter: postgresql
      config:
        dsn: "postgresql://user:password@postgres:5432/abi"
        schema: abi_document
        connect_timeout: 5
        statement_timeout: 30000
        pool_max_size: 10
        pool_timeout: 5.0
```

Render credentials through the deployment's secret service; do not log DSNs.
The standard `custom` adapter loader is also supported.
Root and scaffold `config.remote.yaml` select PostgreSQL through the deployment's
existing `POSTGRES_*` secrets, as does the Docker configuration. They reuse the
configured database; it must exist before boot.

## Migrations and operations

Adding document data fields requires no table migration. Renames and semantic
changes still need data migrations. Keep an application `_schema: int` in the
document, distinct from `Document.version` (the CAS counter), and centralize
upcasting at the module's secondary adapter boundary. Use idempotent resumable
backfills with version checks when retiring old shapes. Index changes remain
migrations; adding uniqueness scans/validates existing state and can lock writers.

Back up the documents table and collection catalog together. For SQLite, use a
SQLite-aware backup or stop writers and capture the file with its WAL; copying
only an active main file can lose committed writes. PostgreSQL uses ordinary
database backup/restore. Switching adapter configuration does not migrate data.

## Tests

From the repository root:

```bash
make test-document-core
uv run pytest libs/naas-abi-core/naas_abi_core/services/document libs/naas-abi-core/naas_abi_core/engine/engine_configuration/EngineConfiguration_DocumentService_test.py -q
DOCUMENT_TEST_POSTGRES_DSN='postgresql://localhost/test' uv run pytest libs/naas-abi-core/naas_abi_core/services/document -q
```

The PostgreSQL fixture creates a random test schema and removes it afterward. It
requires an existing test database and schema-creation permission; without the
environment variable its integration tests explicitly skip. A configured but
unreachable database fails tests rather than skipping. Standard `make deps`,
`make check-core`, and `make test` remain the development entry points.
PR CI runs `make test-document-core` on Python 3.11/3.12 with a PostgreSQL 17 service,
covering both backends, direct port/codec/compiler tests, and engine configuration.

## Adding a new adapter

Implement every protocol method, including transactional CAS and sparse
uniqueness. Subclass `DocumentSecondaryAdapterContract` and provide its `adapter`
fixture. Run the full contract against a real backend. Add factory/configuration
wiring, adapter-specific lifecycle tests, and update this guide. Do not introduce
backend-specific methods into the module-facing port.
