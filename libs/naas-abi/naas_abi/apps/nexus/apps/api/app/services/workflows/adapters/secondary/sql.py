"""``RunOwnersPort`` on the Nexus database (``workflow_run_owners``), one
session per call: the workflows routes hold none."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.models import WorkflowRunOwnerModel
from naas_abi.apps.nexus.apps.api.app.services.workflows.port import (
    RunOwner,
    RunOwnersPort,
)
from sqlalchemy import select


def _owner(row: WorkflowRunOwnerModel) -> RunOwner:
    return RunOwner(
        module_id=str(row.module_id),
        run_id=str(row.run_id),
        workflow=str(row.workflow),
        user_id=str(row.user_id),
        workspace_id=str(row.workspace_id),
        started_at=row.started_at,  # type: ignore[arg-type]
    )


class SqlRunOwners(RunOwnersPort):
    def __init__(self, sessions: Callable[[], Any]) -> None:
        self._sessions = sessions

    async def record(self, owner: RunOwner) -> None:
        async with self._sessions() as db:
            row = await db.get(WorkflowRunOwnerModel, (owner.module_id, owner.run_id))
            if row is None:
                row = WorkflowRunOwnerModel(module_id=owner.module_id, run_id=owner.run_id)
                db.add(row)
            row.workflow = owner.workflow
            row.user_id = owner.user_id
            row.workspace_id = owner.workspace_id
            row.started_at = owner.started_at.replace(tzinfo=None)
            await db.commit()

    async def get(self, module_id: str, run_id: str) -> RunOwner | None:
        async with self._sessions() as db:
            row = await db.get(WorkflowRunOwnerModel, (module_id, run_id))
            return _owner(row) if row is not None else None

    async def list_for(self, user_id: str, workspace_id: str, limit: int) -> list[RunOwner]:
        async with self._sessions() as db:
            result = await db.execute(
                select(WorkflowRunOwnerModel)
                .where(
                    (WorkflowRunOwnerModel.user_id == user_id)
                    & (WorkflowRunOwnerModel.workspace_id == workspace_id)
                )
                .order_by(WorkflowRunOwnerModel.started_at.desc())
                .limit(limit)
            )
            return [_owner(row) for row in result.scalars().all()]
