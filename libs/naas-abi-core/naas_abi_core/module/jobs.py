"""Job API for engine modules: the same declarations as SDK modules.

Engine modules may also use sync handlers; the engine runs them in a worker
thread. Workflows (``naas_abi_core.module.workflows``) are jobs too, with sync
handlers allowed the same way. Without ``naas-abi-sdk`` (core installed without
``[nats]``), inert stand-ins keep modules importable; jobs need NATS mode to run
anyway. See docs/adr/20261001_nats-jobs.md and
docs/adr/20261025_durable-workflows-on-nats.md.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

try:
    from naas_abi_sdk.jobs import (
        Cron,
        Every,
        JobContext,
        JobDescriptor,
        JobsNotHosted,
        OnEvent,
        job,
    )
    from naas_abi_sdk.jobs import JobsMixin as _SDKJobsMixin

    JOBS_AVAILABLE = True

    class JobsMixin(_SDKJobsMixin):
        """The SDK's job declarations, with sync workflow handlers.

        ``@workflow`` on a sync method (``naas_abi_core.module.workflows``) and
        ``declare_workflow`` with a sync handler bind a handler the engine runs in
        a worker thread, with a ``SyncFlowContext``.
        """

        @property
        def _job_handlers(self) -> dict[str, Callable[..., Any]]:
            handlers = _SDKJobsMixin._job_handlers.fget(self)  # type: ignore[attr-defined]
            if "_abi_sync_flows_bound" not in self.__dict__:
                from naas_abi_core.module.workflows import sync_workflow_handler

                for name, attr_name in self._decorated_jobs.items():
                    spec = getattr(
                        getattr(self, attr_name), "__abi_sync_workflow__", None
                    )
                    if spec is not None:
                        handlers[name] = sync_workflow_handler(handlers[name], spec)
                self.__dict__["_abi_sync_flows_bound"] = True
            return handlers

        def workflow_spec(self, name: str) -> Any:
            attr_name = self._decorated_jobs.get(name)
            spec = (
                getattr(getattr(self, attr_name), "__abi_sync_workflow__", None)
                if attr_name
                else None
            )
            return spec if spec is not None else super().workflow_spec(name)

        def declare_workflow(
            self,
            name: str,
            handler: Callable[..., Any],
            *,
            input_type: Any = None,
            output_type: Any = None,
            input_schema: dict[str, Any] | str | None = None,
            output_schema: dict[str, Any] | str | None = None,
            description: str = "",
            triggers: tuple[Any, ...] = (),
            max_concurrency: int = 1,
            timeout: timedelta | None = None,
            max_attempts: int = 1,
        ) -> JobDescriptor:
            """``declare_job`` for a workflow: ``async handler(ctx, inp)`` (a
            ``FlowContext``), or a sync ``handler(ctx, inp)`` that the engine runs
            in a worker thread with a ``SyncFlowContext``."""
            options: dict[str, Any] = {
                "input_type": input_type,
                "output_type": output_type,
                "input_schema": input_schema,
                "output_schema": output_schema,
                "description": description,
                "triggers": triggers,
                "max_concurrency": max_concurrency,
                "timeout": timeout,
                "max_attempts": max_attempts,
            }
            from naas_abi_sdk.jobs import is_async_callable

            if is_async_callable(handler):
                return super().declare_workflow(name, handler, **options)
            from naas_abi_core.module.workflows import sync_workflow_handler
            from naas_abi_sdk.workflows import declare_workflow

            # The SDK's declaration, with core's handler for a sync one.
            return declare_workflow(
                self, name, handler, wrap=sync_workflow_handler, **options
            )

except ImportError:  # core without [nats]
    from naas_abi_core.module.jobs_fallback import (  # type: ignore[assignment]
        JOBS_AVAILABLE,
        Cron,
        Every,
        JobContext,
        JobDescriptor,
        JobsMixin,
        JobsNotHosted,
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
    "JobsNotHosted",
    "OnEvent",
    "job",
]
