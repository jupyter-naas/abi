"""Workflows as a script or a super admin sees them: list, start, follow, cancel.

A workflow is a job with ``kind="workflow"`` (sysadmin ``jobs.py``): a typed input
and output and a journal of steps. This domain is the thin use-case layer over the
jobs one, which owns the ports (catalogs, run records, steps, control, audit).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    TERMINAL_STATUSES,
    JobDefinition,
    JobRun,
    WorkflowDetail,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceStatus

# The longest a start may wait for the result: a request is not a job queue.
MAX_WAIT_SECONDS = 120.0
# Idempotency keys travel as a message id header.
MAX_IDEMPOTENCY_KEY = 200


@dataclass(frozen=True)
class Caller:
    """Who starts or cancels: a Nexus user, or the ABI API key (no user id)."""

    via: Literal["user", "api_key"]
    user_id: str = ""


class InvalidIdempotencyKey(ValueError):
    pass


def check_idempotency_key(key: str | None) -> str | None:
    """The key, or None for none; InvalidIdempotencyKey if it cannot be a header value."""
    if key is None or key == "":
        return None
    if len(key) > MAX_IDEMPOTENCY_KEY or any(ord(c) < 0x20 or ord(c) >= 0x7F for c in key):
        raise InvalidIdempotencyKey(
            f"An idempotency key is at most {MAX_IDEMPOTENCY_KEY} printable ASCII characters"
        )
    return key


@dataclass(frozen=True)
class WorkflowList:
    workflows: tuple[JobDefinition, ...]
    sources: dict[str, SourceStatus]


@dataclass(frozen=True)
class WorkflowRunView:
    """A workflow run: its record (status, result, error) and its steps. The
    record's ``result`` is whole here, not the Jobs tab's preview."""

    run: JobRun
    workflow: WorkflowDetail

    @property
    def finished(self) -> bool:
        return self.run.status in TERMINAL_STATUSES


@dataclass(frozen=True)
class Started:
    """A start: the run id the host will record, and the run as it stood when the
    call returned (QUEUED unless it was waited for)."""

    run_id: str
    view: WorkflowRunView
