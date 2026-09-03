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
| `ducklake` | DuckLake catalog backed by SQLite or PostgreSQL, with Parquet/inlined data under `data_path`, on a local path or an object store. Supports catalog snapshots, time travel, JSON, and upsert. |

## Engine config

```yaml
services:
  dataset:
    dataset_adapter:
      adapter: "ducklake"
      config:
        catalog: "sqlite:storage/datastore/datasets.sqlite"
        data_path: "storage/datastore/datasets/"
        max_retries: 10
        retry_base_delay_seconds: 0.05
        retry_max_delay_seconds: 1.0
```

Default is that block.

`data_path` may instead be an object store URI, which keeps table data wherever the
rest of the deployment persists rather than on a container disk. DuckDB cannot guess
a custom endpoint or its credentials, so an S3-compatible store such as MinIO needs
them here:

```yaml
        data_path: "s3://abi/abi/datastore/datasets/"
        s3_endpoint: "http://minio:9000"
        s3_access_key_id: "{{ secret.MINIO_ROOT_USER }}"
        s3_secret_access_key: "{{ secret.MINIO_ROOT_PASSWORD }}"
```

The scheme on `s3_endpoint` sets the SSL default and an endpoint implies path-style
URLs; `s3_use_ssl`, `s3_url_style` and `s3_region` override both. Omit all of them
for AWS with ambient credentials. Setting them alongside a local `data_path` raises,
because that pairing can only mean a store was intended and would not be used.

A remote `data_path` does not make a SQLite catalog shared. A single-process runtime
may deliberately pair the two, but every replica in a scaled deployment must use the
same durable catalog; use PostgreSQL rather than an ephemeral per-container SQLite
file or the replicas will silently diverge.

Without them, a write to an object store fails with HTTP 403 — or, for a batch small
enough for DuckLake to inline in the catalog, appears to succeed while never reaching
the store. Modules that use the service declare `DatasetService` in `ModuleDependencies.services`.

Each write uses a fresh connection and retries the complete transaction up to 10 times for catalog locks/transaction conflicts. Backoff starts at 50 ms, doubles to a 1-second cap, and has +/-25% jitter. SQLite writers sharing one adapter are serialized before the cross-process retry boundary; PostgreSQL writers remain concurrent. PostgreSQL deployment credentials are rendered from the secret service; do not log the catalog DSN.

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
- Configure a retention window with DuckLake's `expire_older_than` option, then run `CALL ducklake_expire_snapshots('abi_datasets')` followed by `CALL ducklake_cleanup_old_files('abi_datasets')`. Never expire snapshots still required by restore/audit policy.
- Moving from a SQLite catalog to PostgreSQL is a metadata migration. A DSN change alone loses snapshot history and any inlined rows.

## Tests

```bash
uv run pytest naas_abi_core/services/dataset naas_abi_core/engine/engine_configuration/EngineConfiguration_DatasetService_test.py -q
```
