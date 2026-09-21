"""Process pending X Proxy media rows on a bounded cadence."""

from __future__ import annotations

import dagster as dg
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.orchestrations.utils._common import (
    has_in_progress_run,
)


class XDatasetMediaOrchestration(DagsterOrchestration):
    """Drain pending ``media_v1`` downloads without blocking ingest."""

    @classmethod
    def New(cls) -> "XDatasetMediaOrchestration":
        job_name = "x_dataset_media_worker"

        @dg.op(name="x_dataset_media_worker_op", tags={"x_dataset_media": "1"})
        def media_worker_op(context) -> dict:
            from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.media_worker import (
                process_pending_media_batch,
            )

            module = ABIModule.get_instance()
            app_cfg = getattr(module.configuration, "app", None)
            dataset_cfg = getattr(app_cfg, "dataset", None) if app_cfg else None
            batch = int(getattr(dataset_cfg, "media_batch_size", 4) or 4)
            return process_pending_media_batch(module, limit=batch)

        @dg.job(name=job_name, executor_def=dg.in_process_executor)
        def media_worker_job():
            media_worker_op()

        @dg.schedule(
            name="x_dataset_media_worker_schedule",
            job=media_worker_job,
            cron_schedule="*/10 * * * *",
            execution_timezone="UTC",
            default_status=dg.DefaultScheduleStatus.RUNNING,
        )
        def media_worker_schedule(context: dg.ScheduleEvaluationContext):
            if has_in_progress_run(context, job_name):
                return dg.SkipReason(f"Job '{job_name}' is already running.")
            return [dg.RunRequest()]

        return cls(
            definitions=dg.Definitions(
                assets=[],
                jobs=[media_worker_job],
                schedules=[media_worker_schedule],
                sensors=[],
            )
        )
