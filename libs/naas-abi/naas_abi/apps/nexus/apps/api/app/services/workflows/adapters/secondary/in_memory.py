from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.workflows.port import RunOwner, RunOwnersPort


class InMemoryRunOwners(RunOwnersPort):
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], RunOwner] = {}

    async def record(self, owner: RunOwner) -> None:
        self.rows[(owner.module_id, owner.run_id)] = owner

    async def get(self, module_id: str, run_id: str) -> RunOwner | None:
        return self.rows.get((module_id, run_id))

    async def list_for(self, user_id: str, workspace_id: str, limit: int) -> list[RunOwner]:
        mine = [
            o for o in self.rows.values() if (o.user_id, o.workspace_id) == (user_id, workspace_id)
        ]
        return sorted(mine, key=lambda o: o.started_at, reverse=True)[:limit]
