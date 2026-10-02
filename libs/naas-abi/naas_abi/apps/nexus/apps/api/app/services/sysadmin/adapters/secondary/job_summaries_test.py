from datetime import timedelta

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.job_summaries import (
    summarize_job,
)
from naas_abi_sdk.jobs import Cron, Every, JobDescriptor, OnEvent


def test_triggers_read_like_their_declaration():
    summary = summarize_job(
        JobDescriptor(
            "ingest",
            "Pulls orders.",
            triggers=(
                Cron("0 0 6 * * *", time_zone="Europe/Paris"),
                Every("10m"),
                OnEvent("evt.x.>"),
            ),
            max_concurrency=2,
            max_attempts=3,
            timeout=timedelta(minutes=5),
        )
    )

    assert summary.triggers == ("cron 0 0 6 * * * Europe/Paris", "every 10m", "event evt.x.>")
    assert (summary.name, summary.description) == ("ingest", "Pulls orders.")
    assert (summary.max_concurrency, summary.max_attempts, summary.timeout_seconds) == (2, 3, 300.0)


def test_manual_only_jobs_have_no_triggers_and_no_timeout():
    summary = summarize_job(JobDescriptor("adhoc"))

    assert summary.triggers == () and summary.timeout_seconds is None
