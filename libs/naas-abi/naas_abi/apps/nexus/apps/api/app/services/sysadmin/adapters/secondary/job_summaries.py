"""SDK job descriptors (engine modules and discovery) as JobSummary values."""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import JobSummary


def describe_trigger(trigger: Any) -> str:
    if hasattr(trigger, "expression"):
        zone = getattr(trigger, "time_zone", "")
        return f"cron {trigger.expression}" + (f" {zone}" if zone else "")
    if hasattr(trigger, "interval"):
        return f"every {trigger.interval}"
    if hasattr(trigger, "subject"):
        return f"event {trigger.subject}"
    return str(trigger)


def summarize_job(descriptor: Any) -> JobSummary:
    timeout = getattr(descriptor, "timeout", None)
    return JobSummary(
        name=descriptor.name,
        description=getattr(descriptor, "description", "") or "",
        triggers=tuple(describe_trigger(t) for t in getattr(descriptor, "triggers", ())),
        max_concurrency=int(getattr(descriptor, "max_concurrency", 1)),
        max_attempts=int(getattr(descriptor, "max_attempts", 1)),
        timeout_seconds=timeout.total_seconds() if timeout is not None else None,
    )
