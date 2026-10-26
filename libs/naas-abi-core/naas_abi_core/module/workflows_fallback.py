"""Workflow declarations when ``naas-abi-sdk`` is not installed (core without ``[nats]``).

Workflows only run in NATS mode, which needs the SDK. Without it, modules that
declare workflows must still import and load: ``workflow`` keeps the declaration
(the engine then logs that it is not hosted) and validates nothing. See
``jobs_fallback``.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from naas_abi_core.module.jobs_fallback import JobContext, JobDescriptor, JobsNotHosted

WORKFLOWS_AVAILABLE = False


class NonRetryable(Exception):
    """A failure another attempt cannot fix: the run fails at once."""


class WorkflowError(Exception):
    """A workflow could not run, or ended without an output."""


class InvalidWorkflowInput(ValueError):
    pass


class InvalidWorkflowOutput(ValueError):
    pass


class StepKeyError(ValueError):
    pass


class StepResultTooLarge(ValueError):
    pass


class SelfCall(ValueError):
    pass


class WorkflowCancelled(Exception):
    pass


class ChildRunFailed(WorkflowError):
    pass


class WorkflowRunFailed(WorkflowError):
    pass


class FlowContext(JobContext):
    """Stand-in: a workflow's context needs the SDK."""


class WorkflowProxy:
    """Stand-in: calling workflows needs the SDK."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise JobsNotHosted("Workflows run in NATS mode, which needs naas-abi-sdk")


class WorkflowRun(WorkflowProxy):
    pass


def workflow(
    name: str | None = None,
    description: str = "",
    *,
    triggers: tuple[Any, ...] = (),
    max_concurrency: int = 1,
    timeout: timedelta | None = None,
    max_attempts: int = 1,
    input_schema: dict[str, Any] | str | None = None,
    output_schema: dict[str, Any] | str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorate(method: Callable[..., Any]) -> Callable[..., Any]:
        doc = inspect.getdoc(method) or ""
        method.__abi_job__ = JobDescriptor(  # type: ignore[attr-defined]
            name=name or method.__name__,
            description=description or (doc.splitlines()[0] if doc else ""),
            triggers=tuple(triggers),
            max_concurrency=max_concurrency,
            timeout=timeout,
            max_attempts=max_attempts,
            kind="workflow",
        )
        return method

    return decorate
