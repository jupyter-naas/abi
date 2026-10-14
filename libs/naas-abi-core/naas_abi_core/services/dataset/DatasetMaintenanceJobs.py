"""Dataset file maintenance as engine jobs (was the Dagster DatasetCompaction app).

Not a module: the engine hosts these jobs under ``DATASET_JOBS_OWNER`` whenever
the dataset service is loaded in NATS mode, on its own dataset service (no RPC
hop when the engine owns it). Handlers are sync and run in a worker thread.
Payload keys for a manual trigger: ``namespace``, ``name``,
``inline_warning_threshold``; ``dry_run`` for ``dataset_cleanup``.

``flush`` and ``compact`` take as long as the data: when the service is remote
they wait ``call_timeout``, not a client's default of seconds.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from naas_abi_core.module.jobs import Cron, JobContext, JobsMixin, job
from naas_abi_core.services.dataset.DatasetService import DatasetService

DATASET_JOBS_OWNER = "naas_abi_core.dataset"
DEFAULT_INLINE_WARNING_THRESHOLD = 100_000
MAINTENANCE_CALL_TIMEOUT = timedelta(hours=6)


class DatasetMaintenanceJobs(JobsMixin):
    _sync_jobs = True

    def __init__(
        self,
        service: DatasetService,
        *,
        call_timeout: timedelta = MAINTENANCE_CALL_TIMEOUT,
    ) -> None:
        self.service = service
        self.call_timeout = call_timeout

    def _threshold(self, ctx: JobContext) -> int:
        return int(
            ctx.payload.get(
                "inline_warning_threshold", DEFAULT_INLINE_WARNING_THRESHOLD
            )
        )

    @job(
        "dataset_compaction",
        triggers=(Cron("0 0 2 * * *", time_zone="UTC"),),
    )
    def compact(self, ctx: JobContext) -> dict[str, Any]:
        """Flush inline data, then rewrite files with deletes and merge small
        files within partitions; preserve snapshots."""
        namespace = ctx.payload.get("namespace")
        name = ctx.payload.get("name")
        if name is not None:
            datasets = [self.service.describe(name, namespace=namespace or "default")]
        else:
            datasets = self.service.list(namespace=namespace)
        processed = 0
        deadline = self.call_timeout.total_seconds()
        for dataset in datasets:
            if ctx.cancelled.is_set():
                ctx.log("Cancelled; remaining datasets left for the next run")
                break
            self.service.check_catalog_pressure(
                dataset.name,
                namespace=dataset.namespace,
                threshold_records=self._threshold(ctx),
            )
            flushed = self.service.flush(
                dataset.name, namespace=dataset.namespace, timeout_seconds=deadline
            )
            ctx.log(f"Flushed {dataset.namespace}.{dataset.name}: {flushed.rows}")
            compacted = self.service.compact(
                dataset.name, namespace=dataset.namespace, timeout_seconds=deadline
            )
            ctx.log(f"Compacted {dataset.namespace}.{dataset.name}: {compacted.rows}")
            processed += 1
        return {"datasets_processed": processed}

    @job(
        "dataset_cleanup",
        triggers=(Cron("0 0 3 * * *", time_zone="UTC"),),
    )
    def clean_up(self, ctx: JobContext) -> dict[str, Any]:
        """Expire snapshots past the catalog's retention, if it has one, then
        delete the files no snapshot uses (compaction's replaced files among
        them). Skipped when the adapter keeps no such files."""
        clean_up = getattr(self.service.adapter, "clean_up", None)
        if clean_up is None:
            ctx.skip("The dataset adapter keeps no files to clean up")
            return {}
        report = clean_up(dry_run=bool(ctx.payload.get("dry_run", False)))
        expire, delete = (
            ("Would expire", "would delete") if report["dry_run"] else ("Expired", "deleted")
        )
        retention = report["retention_days"]
        ctx.log(
            f"{expire} {report['snapshots_expired']} snapshots "
            + (
                f"(older than {retention:g} days)"
                if retention is not None
                else "(no retention: snapshots are kept)"
            )
            + f"; {delete} {report['files_deleted']} unused files"
        )
        return report

    @job(
        "dataset_catalog_monitor",
        triggers=(Cron("0 0 * * * *", time_zone="UTC"),),
    )
    def monitor_catalogs(self, ctx: JobContext) -> dict[str, int]:
        """Report accumulated inline records without interrupting ingestion."""
        report = {}
        for dataset in self.service.list():
            report[f"{dataset.namespace}.{dataset.name}"] = (
                self.service.check_catalog_pressure(
                    dataset.name,
                    namespace=dataset.namespace,
                    threshold_records=self._threshold(ctx),
                )
            )
        return report
