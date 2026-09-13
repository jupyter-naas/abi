# Dataset Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/dataset/`. Canonical reference for agents.

## Purpose

Named, partitioned tables that modules **create, write, and query with SQL**. Identity and links stay in the triple store; volume (commits, emails, events) lives here.

The graph can catalog a dataset (`dcat:Dataset`). This service stores the table in DuckLake, with one coherent catalog snapshot shared by every dataset.

## Files

```
dataset/
├── DatasetPort.py                 # IDatasetPort, DatasetSpec, exceptions
├── DatasetService.py              # public service
├── DatasetFactory.py
├── DatasetService_test.py
├── adapters/secondary/
│   ├── DatasetSecondaryAdapterDuckLake.py
│   └── DatasetSecondaryAdapterDuckLake_test.py
├── tests/dataset__secondary_adapter__generic_test.py
└── AGENTS.md
```

## Port (`DatasetPort.py`)

```python
class IDatasetPort:
    def create(spec: DatasetSpec) -> DatasetInfo
    def describe(name, *, namespace="default") -> DatasetInfo
    def list(*, namespace=None) -> list[DatasetInfo]
    def write(name, rows, *, namespace="default", mode="append"|"replace"|"upsert", snapshot_id=None) -> DatasetInfo
    def query(sql, *, namespace="default", snapshot_id=None) -> QueryResult
    def compact(name, *, namespace="default") -> QueryResult
    def flush(name, *, namespace="default") -> QueryResult
    def inlined_row_count(name, *, namespace="default") -> int
    def list_snapshots() -> list[DatasetSnapshotInfo]
    def drop(name, *, namespace="default") -> None
```

`DatasetSpec` carries `name`, `namespace`, columns (`string|integer|bigint|double|boolean|date|timestamp|json`), partitions (`column` + `identity|year|month|day`), and `primary_key`. Primary-key columns must exist. DuckLake does not enforce uniqueness; the key only defines `MERGE INTO` matching for upsert, and ordinary appends can create duplicate keys.

The optional write `snapshot_id` is a catalog-wide compare-and-swap token, not a per-dataset version. A write to any dataset advances it and can cause `DatasetSnapshotConflictError`. Successful mutating writes return the exact snapshot committed by that connection; a no-op returns the current observed snapshot.

Partition transforms are physical layout metadata and do not add query columns; use SQL functions such as `month(author_date)` when filtering. Reserved identifiers (`end`, `start`) are valid schema names but must be quoted in caller SQL (`SELECT "end" FROM time_entries`).

JSON values are parsed and deterministically serialized before DuckDB binds them to native `JSON` columns. Invalid values fail with `DatasetSchemaError`. Upserts reject null primary-key values and duplicate keys within one incoming batch.

## Adapter

| Adapter | Notes |
|---|---|
| `ducklake` | DuckLake catalog backed by SQLite or PostgreSQL, with Parquet/inlined data under `data_path`, on a local path or S3-compatible object storage. Supports catalog snapshots, time travel, JSON, and upsert. |

## Engine config

```yaml
services:
  dataset:
    dataset_adapter:
      adapter: "ducklake"
      config:
        catalog: "sqlite:storage/datasets.sqlite"
        data_path: "storage/datasets/"
        data_inlining_row_limit: 1000
        max_retries: 10
        retry_base_delay_seconds: 0.05
        retry_max_delay_seconds: 1.0
```

Default is that block.

The adapter passes `DATA_INLINING_ROW_LIMIT` on every connection, including fresh
connections used by retries. It is a per-insert row limit, not an accumulated
catalog limit. Set it to 0 to disable inlining. Persisted DuckLake table, schema,
or catalog overrides take precedence; this default does not rewrite those options
or change connections opened outside the service. Larger inserts still use Parquet.

`data_path` may instead use an `s3://` or `s3a://` URI, which keeps table data
wherever the deployment persists datasets rather than on a container disk. Other
schemes are rejected until the adapter can configure their native DuckDB secret
types. DuckDB cannot guess a custom endpoint or its credentials, so an S3-compatible
store such as MinIO needs them here:

```yaml
        data_path: "s3://abi/abi/datasets/"
        s3_endpoint: "http://minio:9000"
        s3_access_key_id: "{{ secret.MINIO_ROOT_USER }}"
        s3_secret_access_key: "{{ secret.MINIO_ROOT_PASSWORD }}"
```

The scheme on `s3_endpoint` sets the SSL default and an endpoint implies path-style
URLs; `s3_use_ssl`, `s3_url_style` and `s3_region` override both. A scheme-less
endpoint such as `minio:9000` must set `s3_use_ssl` explicitly so transport security
is never guessed. Omit all of them for AWS with ambient credentials. Setting them
alongside a local `data_path` raises, because that pairing can only mean a store was
intended and would not be used.

A remote `data_path` does not make a SQLite catalog shared. A single-process runtime
may deliberately pair the two, but every replica in a scaled deployment must use the
same durable catalog; use PostgreSQL rather than an ephemeral per-container SQLite
file or the replicas will silently diverge.

Without them, a write to an object store fails with HTTP 403 — or, for a batch small
enough for DuckLake to inline in the catalog, appears to succeed while never reaching
the store. Modules that use the service declare `DatasetService` in `ModuleDependencies.services`.

Each write uses a fresh connection and retries the complete transaction up to 10 times for catalog locks/transaction conflicts. Backoff starts at 50 ms, doubles to a 1-second cap, and has +/-25% jitter. SQLite writers sharing one adapter are serialized before the cross-process retry boundary; PostgreSQL writers remain concurrent. PostgreSQL deployment credentials are rendered from the secret service; do not log the catalog DSN.

Reads (`describe`, `list`, `list_snapshots`, and `query` without a pinned
`snapshot_id`) do not pay that fresh-connection cost: they share one
lazily-created, kept-open connection for the adapter's lifetime, each call
using its own cursor off it. LOAD-ing the `ducklake`/`httpfs` extensions and
ATTACH-ing the catalog dominates a single call's latency, and a long-held
ATTACH observes commits made through other connections without
re-attaching — so this is a pure latency win with no read-staleness
trade-off. One caveat: because the connection is kept open for the process's
lifetime, it does not re-run `_configure_object_store`'s `CREATE OR REPLACE
SECRET`, so a deployment that rotates S3/MinIO credentials at runtime needs
the process restarted (or the adapter recreated) to pick up new ones — a
fresh-per-call connection previously did this implicitly. Pinned
`query(snapshot_id=...)` calls reuse up to four snapshot-specific connections,
with a 60-second lifetime checked on cache access. `SNAPSHOT_VERSION` is fixed
at ATTACH time, so these remain separate from the latest-snapshot connection.
Every query still validates snapshot existence through the DuckLake metadata
`ducklake_snapshot` primary key rather than listing the entire snapshot history,
and uses an independent cursor.
Eviction drops cache ownership without closing active readers' connections.
Flush clears the snapshot cache; a failed pinned query retires its connection
without replaying SQL. These are bounded process-local connection defaults,
not a result cache or a change to snapshot retention.

Ambiguous object-store transport failures are not replayed automatically: a timeout
may arrive after metadata committed, and replaying an append could duplicate rows.
Such failures surface to the caller until the port has an idempotency or commit-status
reconciliation contract.

Every connection attaches with `AUTOMATIC_MIGRATION`, so the adapter initializes a new DuckLake metadata schema or upgrades an older compatible schema. The PostgreSQL database and grants must already exist; those require server-level provisioning outside the catalog connection.

## Operations

- Treat the catalog and `data_path` as one stateful unit, including when `data_path` is a bucket: a catalog restored to a different point than the store references Parquet files that are not there. The SQLite catalog can contain inlined rows, so copying only Parquet files is not a backup.
- `abi stack snapshot create` stops the stack, then captures `postgres_data` and `storage/`; this produces a coherent local-deployment backup for both PostgreSQL and SQLite catalogs.
- Flush inlined rows before storage-only maintenance with `CALL ducklake_flush_inlined_data('abi_datasets')`.
- Compact adjacent small files with `CALL ducklake_merge_adjacent_files('abi_datasets')`.
- Application callers can use `service.compact(name, namespace="default")`, which
  returns maintenance statistics and uses the adapter's write conflict retries.
  It preserves partitions and snapshots and does not flush inlined data or delete
  old files. Missing datasets raise `DatasetNotFoundError`.
- Dagster registers `dataset_compaction_job` when the service is enabled. Launch it
  manually or use `dataset_compaction_daily` (02:00 UTC, running by default).
  The job calls `flush` before `compact` for each dataset, even for small totals.
  Flushing and compaction are separate transactions, both with adapter retries.
  A failed flush prevents compaction of that dataset. A failed compaction leaves
  successfully flushed data intact for the next run.
  Flush retires this adapter's cached read connection because DuckLake can drop
  old inline tables. If another process flushes, an affected cached reader can
  report a stale inline-table error once; the adapter retires that connection so
  the next call reattaches. Arbitrary `query()` SQL is not replayed automatically
  because it can contain writes or multiple statements.
  Optional op config selects `namespace` and `name`; otherwise it processes all
  service datasets. See `../../apps/dagster/AGENTS.md` for run config and semantics.
- `inlined_row_count` reads DuckLake's inline-table registry and counts insertion
  records across schema versions, including deleted/historical records still in
  the inline tables. It does not scan Parquet. It excludes separate inline delete
  markers and does not measure catalog bytes or total metadata/history overhead.
  The adapter owns access to these DuckLake 1.0 metadata tables.
- `service.check_catalog_pressure(name, namespace=..., threshold_records=100_000)`
  logs a warning and publishes `DatasetCatalogPressure` through the engine-wired
  event service on each check at or above the threshold. This follows the existing
  core service `ServiceBase` event wiring convention. Publication is fail-open;
  failures are logged. Without an event service, the warning is still logged.
  The event is defined under `ontologies/classes/ontology_naas_ai/abi/dataset/` and
  described by `ontologies/modules/DatasetEventOntology.ttl`; it inherits the
  canonical `LogProcess` contract. It signals accumulation, not data loss.
- `dataset_catalog_monitor_hourly` checks all datasets hourly without flushing.
  The daily maintenance job also checks before flushing. Both schedules default
  to running but require the Dagster daemon; persisted stopped overrides remain
  stopped. Checks are outside the write path and warnings repeat while over limit.
- Configure a retention window with DuckLake's `expire_older_than` option, then run `CALL ducklake_expire_snapshots('abi_datasets')` followed by `CALL ducklake_cleanup_old_files('abi_datasets')`. Never expire snapshots still required by restore/audit policy.
- Moving from a SQLite catalog to PostgreSQL is a metadata migration. A DSN change alone loses snapshot history and any inlined rows.

## Tests

```bash
uv run pytest naas_abi_core/services/dataset naas_abi_core/engine/engine_configuration/EngineConfiguration_DatasetService_test.py -q
```
