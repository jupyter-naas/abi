# Dataset Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/dataset/`. Canonical reference for agents.

## Purpose

Named, partitioned tables that modules **create, write, and query with SQL**. Identity and links stay in the triple store; volume (commits, emails, events) lives here.

The graph can catalog a dataset (`dcat:Dataset`). This service stores the table. Snapshot / branch arguments default to current so Iceberg + Nessie can plug in later without changing callers.

## Files

```
dataset/
├── DatasetPort.py                 # IDatasetPort, DatasetSpec, exceptions
├── DatasetService.py              # public service
├── DatasetFactory.py
├── DatasetService_test.py
├── adapters/secondary/
│   ├── DatasetSecondaryAdapterDuckDB.py
│   └── DatasetSecondaryAdapterDuckDB_test.py
├── tests/dataset__secondary_adapter__generic_test.py
└── AGENTS.md
```

## Port (`DatasetPort.py`)

```python
class IDatasetPort:
    def create(spec: DatasetSpec) -> DatasetInfo
    def describe(name, *, namespace="default") -> DatasetInfo
    def list(*, namespace=None) -> list[DatasetInfo]
    def write(name, rows, *, namespace="default", mode="append"|"replace", snapshot_id=None) -> DatasetInfo
    def query(sql, *, namespace="default", snapshot_id=None) -> QueryResult
    def drop(name, *, namespace="default") -> None
```

`DatasetSpec` carries `name`, `namespace`, `columns` (`string|integer|bigint|double|boolean|date|timestamp`), and `partitions` (`column` + `identity|year|month|day`).

SQL tables are registered by dataset **name** inside `namespace`. Partition transforms other than `identity` appear as `{column}_{transform}` (e.g. `author_date_month=2026-08`). The DuckDB adapter double-quotes column names on write so reserved words (`end`, `start`) are valid schema names; quote them in SQL too (`SELECT "end" FROM time_entries`).

## Adapter

| Adapter | Notes |
|---|---|
| `duckdb` | Hive-partitioned Parquet under `base_path/{namespace}/{name}/`. DuckDB in-process. Same layout works on a filesystem, MinIO mount, or object-storage prefix. |

## Engine config

```yaml
services:
  dataset:
    dataset_adapter:
      adapter: "duckdb"
      config:
        base_path: "storage/datastore/datasets"
```

Default is that block. Modules that use the service declare `DatasetService` in `ModuleDependencies.services`.

## Tests

```bash
uv run pytest naas_abi_core/services/dataset naas_abi_core/engine/engine_configuration/EngineConfiguration_DatasetService_test.py -q
```
