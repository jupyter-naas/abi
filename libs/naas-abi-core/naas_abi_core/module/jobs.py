"""Job API for engine modules: the same declarations as SDK modules.

Engine modules may also use sync handlers; the engine runs them in a worker
thread. Without ``naas-abi-sdk`` (core installed without ``[nats]``), inert
stand-ins keep modules importable; jobs need NATS mode to run anyway. See
docs/adr/20261001_nats-jobs.md.
"""

try:
    from naas_abi_sdk.jobs import (
        Cron,
        Every,
        JobContext,
        JobDescriptor,
        JobsMixin,
        OnEvent,
        job,
    )

    JOBS_AVAILABLE = True
except ImportError:  # core without [nats]
    from naas_abi_core.module.jobs_fallback import (  # type: ignore[assignment]
        JOBS_AVAILABLE,
        Cron,
        Every,
        JobContext,
        JobDescriptor,
        JobsMixin,
        OnEvent,
        job,
    )

__all__ = [
    "JOBS_AVAILABLE",
    "Cron",
    "Every",
    "JobContext",
    "JobDescriptor",
    "JobsMixin",
    "OnEvent",
    "job",
]
