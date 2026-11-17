"""``CodingEnvironmentStorePort`` in memory, for tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.port import (
    CodingEnvironmentRecord,
    CodingEnvironmentStorePort,
    CodingWorkspace,
    EnvironmentAlreadyRecorded,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class MemoryCodingEnvironmentStore(CodingEnvironmentStorePort):
    def __init__(
        self,
        workspaces: list[CodingWorkspace] | None = None,
        environments: list[CodingEnvironmentRecord] | None = None,
    ) -> None:
        self.workspaces: dict[str, CodingWorkspace] = {w.id: w for w in workspaces or []}
        self.environments: dict[str, CodingEnvironmentRecord] = {
            e.id: e for e in environments or []
        }

    # -- workspaces ------------------------------------------------------------

    async def get_workspace(self, workspace_id: str) -> CodingWorkspace | None:
        return self.workspaces.get(workspace_id)

    async def set_default_repo(self, workspace_id: str, repo_id: str) -> bool:
        workspace = self.workspaces.get(workspace_id)
        if workspace is None:
            return False
        self.workspaces[workspace_id] = replace(workspace, coding_default_repo_id=repo_id)
        return True

    async def default_repos(self) -> list[tuple[str, str]]:
        return [
            (w.id, w.coding_default_repo_id)
            for w in self.workspaces.values()
            if w.coding_default_repo_id is not None
        ]

    # -- environments ----------------------------------------------------------

    async def get(self, environment_id: str) -> CodingEnvironmentRecord | None:
        return self.environments.get(environment_id)

    async def list_all(self) -> list[CodingEnvironmentRecord]:
        return list(self.environments.values())

    async def repos_by_environment(
        self, workspace_id: str, environment_ids: list[str]
    ) -> dict[str, str | None]:
        wanted = set(environment_ids)
        return {
            e.id: e.repo_id
            for e in self.environments.values()
            if e.workspace_id == workspace_id and e.id in wanted
        }

    async def find_by_labels(
        self, *, workspace_id: str, user_id: str, labels: list[str]
    ) -> list[CodingEnvironmentRecord]:
        wanted = set(labels)
        return [
            e
            for e in self.environments.values()
            if e.workspace_id == workspace_id and e.user_id == user_id and e.label in wanted
        ]

    async def add(self, environment: CodingEnvironmentRecord) -> None:
        if environment.id in self.environments:
            raise EnvironmentAlreadyRecorded(environment.id)
        self.environments[environment.id] = replace(
            environment, created_at=environment.created_at or _now()
        )

    async def bind(self, environment: CodingEnvironmentRecord) -> None:
        for other in list(self.environments.values()):
            if (
                other.id != environment.id
                and other.workspace_id == environment.workspace_id
                and other.user_id == environment.user_id
                and other.label == environment.label
            ):
                del self.environments[other.id]
        stored = self.environments.get(environment.id)
        created = environment.created_at or (stored.created_at if stored else None) or _now()
        self.environments[environment.id] = replace(environment, created_at=created)

    async def update_sidecar(
        self, environment_id: str, *, sidecar_base: str | None, sidecar_secret: str | None
    ) -> None:
        stored = self.environments.get(environment_id)
        if stored is not None:
            self.environments[environment_id] = replace(
                stored, sidecar_base=sidecar_base, sidecar_secret=sidecar_secret
            )

    async def delete(self, environment_id: str) -> None:
        self.environments.pop(environment_id, None)
