# Dataset compaction through Dagster

Status: Accepted

Date: 2026-09-10

## Context

Repeated dataset writes can leave small Parquet files in DuckLake partitions.
The Dagster application currently discovers module orchestrations, while dataset
maintenance belongs to the core service and must use its configured catalog and
object-store credentials.

## Decision

Expose per-dataset `flush` and `compact` through the existing dataset port
and service, returning the existing `QueryResult` statistics type. Keep maintenance
SQL and transaction conflict retries in the DuckLake secondary adapter. Register a
built-in Dagster job at the application composition root when datasets are enabled,
injecting the engine service as a resource alongside existing module definitions.

Offer manual execution and a daily schedule at 02:00 UTC, running by default.
Process datasets sequentially, with optional namespace/name selection, flushing
before compacting each dataset. Reuse the
adapter's existing retry and SQLite serialization policy, without Dagster retries.
Default the adapter's per-connection inlining limit to 1,000 rows, configurable
through `data_inlining_row_limit`. Honor persisted catalog/schema/table overrides.
Do not rewrite catalog settings during attach, which would add metadata writes
to every operation and override operator choices. External writers must configure
their own limit or use a persisted DuckLake option.

Expose `inlined_row_count` for periodic pressure checks, using DuckLake 1.0's
inline-table registry inside the adapter. Count physical insertion records across
schema versions, including historical/deleted records, rather than pretending to
measure total catalog bytes. Separate inline deletion markers are not counted.

Add an hourly Dagster monitor with a configurable 100,000-record warning threshold
per dataset. The daily job also checks before flushing. Emit `DatasetCatalogPressure`
using the canonical LogProcess event contract and existing ServiceBase event wiring,
with fail-open publication. These are core framework services; reuse their existing
event communication contract. Do not introduce another cross-domain transport or
new persistence adapter. Keep monitoring off the ingestion path. Warnings repeat
on each over-limit check; the threshold is advisory, not an enforced storage limit.
Use service warnings, Dagster logs, and output metadata for observability.

## Consequences

The service stays independent of Dagster. Every dataset adapter must implement the
new port methods. Each flush and compaction commits independently; failures are visible as failed
runs, and reruns may revisit completed datasets. The job preserves snapshot history
and partition boundaries. It does not expire snapshots, delete
old files, or guarantee one output file per partition. Table-level compaction is
explicit, so bulk-call `auto_compact` exclusions do not apply. Operators run the
Dagster daemon to automate execution; saved stopped schedule overrides still need
to be enabled. Flushing alone does not guarantee that the catalog's on-disk file
shrinks. PostgreSQL and SQLite database maintenance remains separate.

The current DuckLake extension can retain stale inline-table references on a
kept-open read connection after flushing old schema versions. Retire the local
cached connection after flushing. A stale-inline-table failure caused by another
process also retires the connection, but the failed call is surfaced; the next
call reattaches. Do not automatically replay arbitrary SQL exposed by `query`,
which permits mutations and multi-statement requests.
