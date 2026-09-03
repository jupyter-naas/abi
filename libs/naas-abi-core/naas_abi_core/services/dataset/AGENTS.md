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

`DatasetSpec` carries `name`, `namespace`, columns (`string|integer|bigint|double|boolean|date|timestamp|json`), partitions (`column` + `identity|year|month|day`), and `primary_key`. Primary-key columns must exist. DuckLake does not enforce uniqueness; the key defines `MERGE INTO` matching for upsert.

Partition transforms are physical layout metadata and do not add query columns; use SQL functions such as `month(author_date)` when filtering. Reserved identifiers (`end`, `start`) are valid schema names but must be quoted in caller SQL (`SELECT "end" FROM time_entries`).

JSON values are parsed and deterministically serialized before DuckDB binds them to native `JSON` columns. Invalid values fail with `DatasetSchemaError`. Upserts reject null primary-key values and duplicate keys within one incoming batch.

## Adapter

| Adapter | Notes |
|---|---|
| `ducklake` | DuckLake catalog backed by SQLite or PostgreSQL, with Parquet/inlined data under `data_path`. Supports catalog snapshots, time travel, JSON, and upsert. |

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

Default is that block. Modules that use the service declare `DatasetService` in `ModuleDependencies.services`.

Each write uses a fresh connection and retries the complete transaction up to 10 times for catalog locks/transaction conflicts. Backoff starts at 50 ms, doubles to a 1-second cap, and has +/-25% jitter. SQLite writers sharing one adapter are serialized before the cross-process retry boundary; PostgreSQL writers remain concurrent. PostgreSQL deployment credentials are rendered from the secret service; do not log the catalog DSN.

## Operations

- Treat the catalog and `data_path` as one stateful unit. The SQLite catalog can contain inlined rows, so copying only Parquet files is not a backup.
- `abi stack snapshot create` stops the stack, then captures `postgres_data` and `storage/`; this produces a coherent local-deployment backup for both PostgreSQL and SQLite catalogs.
- Flush inlined rows before storage-only maintenance with `CALL ducklake_flush_inlined_data('abi_datasets')`.
- Compact adjacent small files with `CALL ducklake_merge_adjacent_files('abi_datasets')`.
- Configure a retention window with DuckLake's `expire_older_than` option, then run `CALL ducklake_expire_snapshots('abi_datasets')` followed by `CALL ducklake_cleanup_old_files('abi_datasets')`. Never expire snapshots still required by restore/audit policy.
- Moving from a SQLite catalog to PostgreSQL is a metadata migration. A DSN change alone loses snapshot history and any inlined rows.

## Tests

```bash
uv run pytest naas_abi_core/services/dataset naas_abi_core/engine/engine_configuration/EngineConfiguration_DatasetService_test.py -q
```
