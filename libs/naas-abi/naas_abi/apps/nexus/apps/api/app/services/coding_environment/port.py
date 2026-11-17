"""Secondary port: what Nexus records about its coding environments.

Coder (or the local runtime) owns an environment's lifecycle; Nexus records
which Nexus workspace and user an environment was provisioned for, the repository
it was cloned from, the runtime label (``slides/<slug>``, ``documents/...``, a
code runtime) and the sidecar it is reached through. The workspace's default
repository is read and set here too: it is the only workspace field the coding
routes use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


class EnvironmentAlreadyRecorded(Exception):
    """An environment with that id is already recorded."""


@dataclass(frozen=True)
class CodingEnvironmentRecord:
    """One environment Nexus provisioned (``id`` is the runtime's workspace id)."""

    id: str
    workspace_id: str
    user_id: str
    repo_id: str | None = None
    label: str | None = None
    sidecar_base: str | None = None
    sidecar_secret: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class CodingWorkspace:
    """The fields of a Nexus workspace the coding routes read."""

    id: str
    organization_id: str | None = None
    coding_default_repo_id: str | None = None


class CodingEnvironmentStorePort(ABC):
    """Environment bindings and the workspace's default repository.

    Writes are applied when the method returns; a failed write raises and
    leaves nothing applied. Callers that treat the record as bookkeeping catch
    the error themselves.
    """

    # -- workspaces ------------------------------------------------------------

    @abstractmethod
    async def get_workspace(self, workspace_id: str) -> CodingWorkspace | None:
        """The workspace, or None when there is none with that id."""

    @abstractmethod
    async def set_default_repo(self, workspace_id: str, repo_id: str) -> bool:
        """Set the workspace's default repository; False when there is no such workspace."""

    @abstractmethod
    async def default_repos(self) -> list[tuple[str, str]]:
        """``(workspace id, repo id)`` of every workspace with a default repository."""

    # -- environments ----------------------------------------------------------

    @abstractmethod
    async def get(self, environment_id: str) -> CodingEnvironmentRecord | None:
        """The environment with that id, or None."""

    @abstractmethod
    async def list_all(self) -> list[CodingEnvironmentRecord]:
        """Every recorded environment, of every workspace."""

    @abstractmethod
    async def repos_by_environment(
        self, workspace_id: str, environment_ids: list[str]
    ) -> dict[str, str | None]:
        """Environment id -> recorded repository, for those of ``environment_ids``
        recorded for the workspace (the others are absent)."""

    @abstractmethod
    async def find_by_labels(
        self, *, workspace_id: str, user_id: str, labels: list[str]
    ) -> list[CodingEnvironmentRecord]:
        """The user's environments in the workspace whose label is one of ``labels``."""

    @abstractmethod
    async def add(self, environment: CodingEnvironmentRecord) -> None:
        """Record a new environment; ``EnvironmentAlreadyRecorded`` when its id is."""

    @abstractmethod
    async def bind(self, environment: CodingEnvironmentRecord) -> None:
        """Make ``environment`` the one binding of its (workspace, user, label):
        the others are removed and it is inserted, or updated in place when its
        id is already recorded (its ``created_at`` is kept)."""

    @abstractmethod
    async def update_sidecar(
        self, environment_id: str, *, sidecar_base: str | None, sidecar_secret: str | None
    ) -> None:
        """Replace the sidecar an environment is reached through (no-op if unknown)."""

    @abstractmethod
    async def delete(self, environment_id: str) -> None:
        """Forget an environment (no-op if unknown)."""
