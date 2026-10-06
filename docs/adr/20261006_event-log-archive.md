# Archiving the event log into the Dataset Service

## Status
Accepted.

## Date
2026-10-06

## Context
Every service write publishes an event, so the event log grows quickly. The
PostgreSQL event log (`20261006_shared-event-and-activity-log-storage.md`) serves
the live uses: publishing, recent queries, replays and consumers. It is not
where months of history should accumulate.

The Dataset Service exists for volume. It stores compressed Parquet, partitioned,
on a shared catalog, and answers SQL. It is a poor live log: each single-row
append is a DuckLake transaction, writes contend on one catalog-wide snapshot
token, and it has no atomic sequence or consumer cursors. It suits history moved
there in batches.

## Decision
Events older than **7 days** move hourly from PostgreSQL into the Dataset Service.

- **Where the job lives.** `EventArchiveJobs` (`event_archive`) sits beside the
  PostgreSQL adapter in `services/event/adapters/secondary/`. The adapter offers
  it through `job_owners(services)`, and `Engine.job_owners()` collects such
  offers from every service's adapter, in NATS mode only, like the other kernel
  jobs. The job runs on the serving engine (`Cron("0 30 * * * *")`, UTC), with
  the engine's own event adapter and the engine's Dataset Service.
- **Where events go.** The dataset `events_archive`, in the namespace named after
  the event schema (`abi_event` by default), partitioned by month of the event's
  UTC date. Columns:
  - `seq`, `id`, `event_type`;
  - `timestamp`, exactly as the log had it;
  - `day`, the partition key;
  - `payload`, as UTF-8 text, else base64, with `payload_encoding` saying which.
- **Exactly once.** The archive's highest `seq` is where the last run stopped. A
  run first deletes from PostgreSQL what an interrupted run archived but did not
  delete. Then it moves batches (10,000 events each by default). Each batch is
  written as one snapshot before its rows are deleted, a chunk per transaction.
- **Never too early.** Archiving stops before the first event newer than the
  window, so a backdated event cannot pull recent ones along. It also stops at
  the lowest cursor of any consumer that read within the window. Consumers idle
  longer than the window are logged and left behind.
- **Numbers are never reused.** The PostgreSQL log numbers events from a one-row
  counter, locked until commit, instead of `MAX(seq) + 1`. Emptying the table
  cannot restart the sequence, and appends stay gapless and visible in order.
- **Config** under the PostgreSQL event adapter: `archive_after_days` (default 7,
  `null` keeps every event) and `archive_batch_rows` (default 10,000).

## Consequences
- The event service reads the last 7 days: queries, `iter_query`, replays,
  consumers and the System app's type counts. Older events are read with SQL on
  the dataset, for example
  `SELECT event_type, count(*) FROM events_archive GROUP BY 1`.
- A consumer idle for more than 7 days misses the events archived meanwhile. A
  warning names it on every run.
- The archive needs the Dataset Service on shared storage (PostgreSQL catalog,
  S3 data) for deploys without downtime. The shared-backend check already
  requires this.
- Each run adds snapshots and files to DuckLake. The daily dataset compaction
  merges the files; snapshot expiry follows the dataset retention policy.
- Reading archived events through the event service (`query` below the archive's
  highest `seq`) is not provided. It can come later without changing the
  archive's layout.
- **Tests,** against a real PostgreSQL and a local DuckLake:
  - age, batches and non-UTF-8 payloads;
  - a run interrupted between write and delete;
  - active and idle consumers, and cancellation;
  - numbering after everything is archived;
  - the engine collecting adapter jobs.
