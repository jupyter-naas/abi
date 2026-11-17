"""Saved graph views in the Nexus database's ``graph_views`` table.

``state`` is stored as JSON text; a row whose text is not a JSON object reads as
an empty state, as it always has.
"""

from __future__ import annotations

import json
from typing import Any

from naas_abi.apps.nexus.apps.api.app.models import GraphViewModel
from naas_abi.apps.nexus.apps.api.app.services.view.port import (
    GraphViewRecord,
    GraphViewStorePort,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


def _state(raw: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _record(model: GraphViewModel) -> GraphViewRecord:
    return GraphViewRecord(
        id=str(model.id),
        workspace_id=str(model.workspace_id),
        name=str(model.name),
        description=model.description,  # type: ignore[arg-type]
        view_type=str(model.view_type),
        kind=str(model.kind),
        visibility=str(model.visibility),
        creator_id=model.creator_id,  # type: ignore[arg-type]
        graph_id=str(model.graph_id),
        graph_uri=str(model.graph_uri),
        state=_state(model.state),
        path=str(model.path or ""),
        created_at=model.created_at,  # type: ignore[arg-type]
        updated_at=model.updated_at,  # type: ignore[arg-type]
    )


def _write(model: GraphViewModel, view: GraphViewRecord) -> None:
    model.name = view.name  # type: ignore[assignment]
    model.description = view.description  # type: ignore[assignment]
    model.view_type = view.view_type  # type: ignore[assignment]
    model.kind = view.kind  # type: ignore[assignment]
    model.visibility = view.visibility  # type: ignore[assignment]
    model.creator_id = view.creator_id  # type: ignore[assignment]
    model.graph_id = view.graph_id  # type: ignore[assignment]
    model.graph_uri = view.graph_uri  # type: ignore[assignment]
    model.state = json.dumps(view.state)  # type: ignore[assignment]
    model.path = view.path  # type: ignore[assignment]


class SqlGraphViewStore(GraphViewStorePort):
    """On the request's session; every write commits."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _model(self, workspace_id: str, view_id: str) -> GraphViewModel | None:
        result = await self._db.execute(
            select(GraphViewModel).where(
                GraphViewModel.id == view_id, GraphViewModel.workspace_id == workspace_id
            )
        )
        return result.scalar_one_or_none()

    async def list(self, workspace_id: str) -> list[GraphViewRecord]:
        result = await self._db.execute(
            select(GraphViewModel).where(GraphViewModel.workspace_id == workspace_id)
        )
        return [_record(model) for model in result.scalars().all()]

    async def get(self, workspace_id: str, view_id: str) -> GraphViewRecord | None:
        model = await self._model(workspace_id, view_id)
        return _record(model) if model is not None else None

    async def add(self, view: GraphViewRecord) -> GraphViewRecord:
        model = GraphViewModel(id=view.id, workspace_id=view.workspace_id)
        _write(model, view)
        self._db.add(model)
        await self._db.commit()
        await self._db.refresh(model)
        return _record(model)

    async def save(self, view: GraphViewRecord) -> GraphViewRecord | None:
        model = await self._model(view.workspace_id, view.id)
        if model is None:
            return None
        _write(model, view)
        await self._db.commit()
        await self._db.refresh(model)
        return _record(model)

    async def delete(self, workspace_id: str, view_id: str) -> bool:
        result = await self._db.execute(
            delete(GraphViewModel).where(
                GraphViewModel.id == view_id, GraphViewModel.workspace_id == workspace_id
            )
        )
        await self._db.commit()
        return bool(getattr(result, "rowcount", 0))

    async def move(self, workspace_id: str, paths: dict[str, str]) -> None:
        if not paths:
            return
        result = await self._db.execute(
            select(GraphViewModel).where(
                GraphViewModel.workspace_id == workspace_id, GraphViewModel.id.in_(list(paths))
            )
        )
        # Per row, in one transaction (portable across PostgreSQL and SQLite).
        for model in result.scalars().all():
            model.path = paths[str(model.id)]  # type: ignore[assignment]
        await self._db.commit()
