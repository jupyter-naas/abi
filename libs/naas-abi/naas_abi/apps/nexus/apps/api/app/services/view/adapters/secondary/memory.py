"""Saved graph views in process memory (tests)."""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.view.port import (
    GraphViewRecord,
    GraphViewStorePort,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _copy(view: GraphViewRecord) -> GraphViewRecord:
    return replace(view, state=copy.deepcopy(view.state))


class MemoryGraphViewStore(GraphViewStorePort):
    def __init__(self) -> None:
        self._views: dict[tuple[str, str], GraphViewRecord] = {}

    async def list(self, workspace_id: str) -> list[GraphViewRecord]:
        return [_copy(view) for (ws, _), view in self._views.items() if ws == workspace_id]

    async def get(self, workspace_id: str, view_id: str) -> GraphViewRecord | None:
        view = self._views.get((workspace_id, view_id))
        return _copy(view) if view is not None else None

    async def add(self, view: GraphViewRecord) -> GraphViewRecord:
        key = (view.workspace_id, view.id)
        if key in self._views:
            raise ValueError(f"View {view.id} already exists")
        now = _now()
        self._views[key] = replace(_copy(view), created_at=now, updated_at=now)
        return _copy(self._views[key])

    async def save(self, view: GraphViewRecord) -> GraphViewRecord | None:
        key = (view.workspace_id, view.id)
        stored = self._views.get(key)
        if stored is None:
            return None
        self._views[key] = replace(_copy(view), created_at=stored.created_at, updated_at=_now())
        return _copy(self._views[key])

    async def delete(self, workspace_id: str, view_id: str) -> bool:
        return self._views.pop((workspace_id, view_id), None) is not None

    async def move(self, workspace_id: str, paths: dict[str, str]) -> None:
        for view_id, path in paths.items():
            key = (workspace_id, view_id)
            if key in self._views:
                self._views[key] = replace(self._views[key], path=path)
