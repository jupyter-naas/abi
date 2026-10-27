"""Who started which workflow run, from which workspace; which workflows and
pipelines a workspace turned off.

A job run carries no owner of its own (its record is the host's, named
``job_run/<project>/<module>/<job>/<run id>``): Nexus records the user and the
workspace of each start it makes from a workspace, and a user reads those runs
alone (``module:ReadWorkflowRuns`` / ``ReadPipelineRuns``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RunOwner:
    module_id: str
    run_id: str
    workflow: str
    user_id: str
    workspace_id: str
    started_at: datetime


class RunOwnersPort(ABC):
    @abstractmethod
    async def record(self, owner: RunOwner) -> None:
        """Remember ``owner``; a run id the jobs stream reuses names the new run."""

    @abstractmethod
    async def get(self, module_id: str, run_id: str) -> RunOwner | None: ...

    @abstractmethod
    async def list_for(self, user_id: str, workspace_id: str, limit: int) -> list[RunOwner]:
        """The user's starts in the workspace, newest first."""


@dataclass(frozen=True)
class WorkflowSwitch:
    """A workflow or pipeline turned on or off in a workspace (``type`` is
    ``workflow`` or ``pipeline``, as its module scope)."""

    workspace_id: str
    type: str
    module_id: str
    name: str
    enabled: bool


class WorkflowVisibilityPort(ABC):
    """On and off per workspace; one never switched is on."""

    @abstractmethod
    async def list_for(self, workspace_id: str) -> list[WorkflowSwitch]:
        """Every switch recorded in the workspace."""

    @abstractmethod
    async def put(self, switch: WorkflowSwitch) -> None:
        """Record ``switch``, replacing the workspace's earlier one for that item."""
