# Dagster application

## Purpose

Composition root for module orchestrations and built-in service maintenance jobs.
Keep Dagster imports here; services and outbound ports remain framework-independent.

## Files

- `dagster.py`: loads the engine and merges module and service definitions.
- `DatasetCompaction.py`: dataset flush/compaction and pressure-monitoring jobs,
  resource binding, and schedules.
- `DatasetCompaction_test.py`: job selection, schedule, empty catalog, and failure tests.

## Port and service API

Inject `DatasetService` through the `dataset_compaction_service` Dagster resource.
The jobs call `list`, `describe`, `check_catalog_pressure`, `flush`, and `compact`;
DuckLake SQL belongs in the dataset
secondary adapter. See `../../services/dataset/AGENTS.md` for the service contract.

## Adapters and factory

`dataset_compaction_definitions(service)` builds the job and schedule with the
engine's configured service. Register only when `dataset_available()` is true.
Preserve module definitions when adding other built-in jobs.

## Operations

Launch `dataset_compaction_job` manually, or use `dataset_compaction_daily` in
Dagster. The schedule defaults to running at 02:00 UTC. Each dataset is checked for
catalog pressure, flushed regardless of its inline count, then compacted.
Scheduled execution requires a running Dagster daemon. A previously saved stopped
schedule remains stopped until explicitly enabled in Dagster.

`dataset_catalog_monitor_job` checks all datasets without flushing or compacting.
Its `dataset_catalog_monitor_hourly` schedule defaults to running hourly, in UTC.
It emits a `DatasetCatalogPressure` event through the service when unflushed
insertion records reach the configured limit. No extra scan is added to writes.

Default run config processes all service datasets sequentially. Optional Launchpad
config targets a namespace or a single dataset:

```yaml
ops:
  compact_datasets:
    config:
      namespace: analytics
      name: events
      inline_warning_threshold: 100000
```

Omit `name` to process every dataset in the namespace; omit both for all namespaces.
A name without a namespace targets `default`. Each flush and compaction has its
own transaction; a failure fails the run and earlier completed work remains
committed. A failed flush prevents the corresponding compaction. Adapter
conflict retries apply; no additional Dagster retries are configured.

The monitoring op uses `ops.check_dataset_catalogs.config.inline_warning_threshold`
with the same 100,000-record default. Set a positive integer. Warnings are emitted
on every over-limit check, including the daily check; they are not a strict size
limit or immediate notification on crossing. Counts include historical/deleted
insertion records, but exclude separate inline delete markers and catalog metadata.
Event publication failure is logged and does not block flushing/compaction.

Maintenance preserves partition boundaries and snapshot history. It does not
expire snapshots or clean up files. Explicit table selection also
means DuckLake's bulk-call `auto_compact` exclusion is not consulted. Compaction
size follows the catalog's `target_file_size` setting; one file per partition per
day is not guaranteed. Logging uses Dagster run
logs for per-dataset results and output metadata for the processed dataset count;
no new metrics or tracing stack is introduced.

## Tests

From the repository root:

```bash
uv run pytest -o addopts='' libs/naas-abi-core/naas_abi_core/apps/dagster libs/naas-abi-core/naas_abi_core/services/dataset
```

## Adding a new adapter

Implement the dataset port including `flush`, `compact`, and `inlined_row_count`;
unsupported maintenance must raise
`NotImplementedError`. Do not add adapter-specific SQL to the Dagster job.
