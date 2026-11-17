"""``CodingEnvironmentStorePort`` on the Nexus database (PostgreSQL or SQLite):
the ``coding_environments`` table and the ``workspaces.coding_default_repo_id``
column, through the request's session."""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.models import CodingEnvironmentModel, WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.port import (
    CodingEnvironmentRecord,
    CodingEnvironmentStorePort,
    CodingWorkspace,
    EnvironmentAlreadyRecorded,
)
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def _record(row: CodingEnvironmentModel) -> CodingEnvironmentRecord:
    return CodingEnvironmentRecord(
        id=str(row.id),
        workspace_id=str(row.workspace_id),
        user_id=str(row.user_id),
        repo_id=row.repo_id,  # type: ignore[arg-type]
        label=row.label,  # type: ignore[arg-type]
        sidecar_base=row.sidecar_base,  # type: ignore[arg-type]
        sidecar_secret=row.sidecar_secret,  # type: ignore[arg-type]
        created_at=row.created_at,  # type: ignore[arg-type]
    )


def _model(environment: CodingEnvironmentRecord) -> CodingEnvironmentModel:
    fields: dict[str, Any] = {
        "id": environment.id,
        "workspace_id": environment.workspace_id,
        "user_id": environment.user_id,
        "repo_id": environment.repo_id,
        "label": environment.label,
        "sidecar_base": environment.sidecar_base,
        "sidecar_secret": environment.sidecar_secret,
    }
    # Left unset, a merge keeps the stored creation time (and an insert takes
    # the column default).
    if environment.created_at is not None:
        fields["created_at"] = environment.created_at
    return CodingEnvironmentModel(**fields)


class SqlCodingEnvironmentStore(CodingEnvironmentStorePort):
    """Every write commits the session it was given; a failed one is rolled back
    and re-raised."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _commit(self) -> None:
        try:
            await self._db.commit()
        except Exception:
            await self._db.rollback()
            raise

    # -- workspaces ------------------------------------------------------------

    async def get_workspace(self, workspace_id: str) -> CodingWorkspace | None:
        row = (
            await self._db.execute(select(WorkspaceModel).where(WorkspaceModel.id == workspace_id))
        ).scalar_one_or_none()
        if row is None:
            return None
        return CodingWorkspace(
            id=str(row.id),
            organization_id=getattr(row, "organization_id", None),
            coding_default_repo_id=getattr(row, "coding_default_repo_id", None),
        )

    async def set_default_repo(self, workspace_id: str, repo_id: str) -> bool:
        row = (
            await self._db.execute(select(WorkspaceModel).where(WorkspaceModel.id == workspace_id))
        ).scalar_one_or_none()
        if row is None:
            return False
        row.coding_default_repo_id = repo_id  # type: ignore[assignment]
        await self._commit()
        return True

    async def default_repos(self) -> list[tuple[str, str]]:
        rows = await self._db.execute(
            select(WorkspaceModel.id, WorkspaceModel.coding_default_repo_id).where(
                WorkspaceModel.coding_default_repo_id.is_not(None)
            )
        )
        return [(workspace, repo) for workspace, repo in rows.all()]

    # -- environments ----------------------------------------------------------

    async def get(self, environment_id: str) -> CodingEnvironmentRecord | None:
        row = await self._db.get(CodingEnvironmentModel, environment_id)
        return _record(row) if row is not None else None

    async def list_all(self) -> list[CodingEnvironmentRecord]:
        rows = await self._db.execute(select(CodingEnvironmentModel))
        return [_record(row) for row in rows.scalars().all()]

    async def repos_by_environment(
        self, workspace_id: str, environment_ids: list[str]
    ) -> dict[str, str | None]:
        if not environment_ids:
            return {}
        rows = await self._db.execute(
            select(CodingEnvironmentModel.id, CodingEnvironmentModel.repo_id).where(
                CodingEnvironmentModel.workspace_id == workspace_id,
                CodingEnvironmentModel.id.in_(environment_ids),
            )
        )
        return dict(rows.all())  # type: ignore[arg-type]

    async def find_by_labels(
        self, *, workspace_id: str, user_id: str, labels: list[str]
    ) -> list[CodingEnvironmentRecord]:
        if not labels:
            return []
        rows = await self._db.execute(
            select(CodingEnvironmentModel).where(
                CodingEnvironmentModel.workspace_id == workspace_id,
                CodingEnvironmentModel.user_id == user_id,
                CodingEnvironmentModel.label.in_(labels),
            )
        )
        return [_record(row) for row in rows.scalars().all()]

    async def add(self, environment: CodingEnvironmentRecord) -> None:
        self._db.add(_model(environment))
        try:
            await self._commit()
        except IntegrityError as exc:
            raise EnvironmentAlreadyRecorded(environment.id) from exc

    async def bind(self, environment: CodingEnvironmentRecord) -> None:
        try:
            # Replace any stale row for this label, then upsert on the id.
            # Re-adopting the same environment keeps its id, so inserting a
            # fresh row would collide on the primary key; merge updates it in
            # place instead.
            prior = await self._db.execute(
                select(CodingEnvironmentModel).where(
                    CodingEnvironmentModel.workspace_id == environment.workspace_id,
                    CodingEnvironmentModel.user_id == environment.user_id,
                    CodingEnvironmentModel.label == environment.label,
                )
            )
            for old in prior.scalars().all():
                if old.id != environment.id:
                    await self._db.delete(old)
            await self._db.merge(_model(environment))
        except Exception:
            await self._db.rollback()
            raise
        await self._commit()

    async def update_sidecar(
        self, environment_id: str, *, sidecar_base: str | None, sidecar_secret: str | None
    ) -> None:
        row = await self._db.get(CodingEnvironmentModel, environment_id)
        if row is None:
            return
        row.sidecar_base = sidecar_base  # type: ignore[assignment]
        row.sidecar_secret = sidecar_secret  # type: ignore[assignment]
        await self._commit()

    async def delete(self, environment_id: str) -> None:
        try:
            await self._db.execute(
                delete(CodingEnvironmentModel).where(CodingEnvironmentModel.id == environment_id)
            )
        except Exception:
            await self._db.rollback()
            raise
        await self._commit()
