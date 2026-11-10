"""Who started which workflow run, from which workspace.

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
