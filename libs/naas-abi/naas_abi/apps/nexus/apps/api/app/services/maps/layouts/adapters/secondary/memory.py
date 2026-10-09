from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import MapsLayout
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.port import MapsLayoutStorePort


class InMemoryMapsLayoutStore(MapsLayoutStorePort):
    """For tests and local runs without Postgres."""

    def __init__(self) -> None:
        self._layouts: dict[str, dict[str, MapsLayout]] = {}
        self._hidden: dict[str, set[str]] = {}

    async def list(self, workspace_id: str) -> list[MapsLayout]:
        return list(self._layouts.get(workspace_id, {}).values())

    async def save(self, workspace_id: str, layout: MapsLayout, *, user_id: str | None) -> None:
        self._layouts.setdefault(workspace_id, {})[layout.id] = layout

    async def delete(self, workspace_id: str, layout_id: str) -> bool:
        return self._layouts.get(workspace_id, {}).pop(layout_id, None) is not None

    async def get_hidden(self, workspace_id: str) -> set[str]:
        return set(self._hidden.get(workspace_id, set()))

    async def set_hidden(
        self, workspace_id: str, layout_ids: set[str], *, user_id: str | None
    ) -> None:
        self._hidden[workspace_id] = set(layout_ids)
