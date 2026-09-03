# DuckLake as the Dataset Service Backend

## Status

Accepted

## Date

2026-09-03

## Context

The dataset service stored Hive-partitioned Parquet through an in-process
DuckDB adapter. Its UUID snapshot value represented only the latest state of
one dataset and could not provide historical reads or a coherent snapshot for
SQL joining multiple datasets. The adapter also lacked native JSON columns and
upsert. Partitioned append failed on a second write because plain DuckDB `COPY`
requires explicit append behavior.

Dataset usage is limited enough that changing the port now is preferable to
preserving snapshot semantics that cannot be implemented honestly.

## Decision

DuckLake is the only built-in dataset adapter. It provides catalog-level,
monotonically increasing integer snapshots, native JSON, partition metadata,
and `MERGE INTO` for upsert. `DatasetSpec.primary_key` records the columns used
to match an upsert because DuckLake does not provide primary-key or unique
constraints.

The zero-infrastructure runtime uses a SQLite catalog at
`storage/datastore/datasets.sqlite`. CLI-created local Docker deployments use
a dedicated PostgreSQL database named `ducklake`. Both use
`storage/datastore/datasets/` for table data.

Every write is retried as a complete transaction on a fresh connection for
retriable attach, lock, serialization, or commit conflicts. The default budget
is 10 retries with exponential backoff from 50 ms to 1 second and +/-25%
jitter. These values favor correctness for shared API/worker catalogs; they are
configurable because workload-specific reliability policy is not yet settled.
SQLite writers sharing one adapter are serialized before this retry boundary;
cross-process SQLite writers and all PostgreSQL writers use the retry policy.

## Consequences

- Snapshot IDs change from per-dataset UUID strings to catalog-level integers.
- A historical query attaches the entire catalog at one version, so every
  table referenced by raw SQL observes the same state.
- Upsert rejects null keys and duplicate keys in an incoming batch. DuckLake
  does not enforce uniqueness for ordinary append operations.
- The plain DuckDB/Parquet adapter is removed because it cannot provide the new
  history and coherent-catalog contract.
- SQLite catalog files may contain inlined table rows. Catalog metadata and the
  data path are therefore one backup/restore unit.
- PostgreSQL credentials are interpolated into the DuckLake catalog DSN at
  runtime. They remain secret configuration and must not be logged.
- Fresh deployments create the `ducklake` database through an idempotent init
  script. Existing PostgreSQL volumes must run that script explicitly.
- Moving a catalog from SQLite to PostgreSQL requires migrating metadata; it is
  not a configuration-only DSN change.
- `data_path` may be a local path or an object store URI. A custom S3 endpoint
  and its credentials are explicit configuration: DuckDB defaults to AWS and
  virtual-hosted URLs, so a store such as MinIO is unreachable without them.
  A misconfigured store does not always fail — a batch small enough to be
  inlined in the catalog commits without the data ever leaving it.
- Operators must schedule data flushing, adjacent-file compaction, snapshot
  expiry, and cleanup according to their retention policy.
