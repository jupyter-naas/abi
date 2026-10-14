from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.feed_layers__schema import (
    MapsFeedLayer,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.port import (
    MapsFeedLayerStorePort,
)


class InMemoryMapsFeedLayerStore(MapsFeedLayerStorePort):
    """For tests and local runs without Postgres."""

    def __init__(self) -> None:
        self._layers: dict[str, dict[str, MapsFeedLayer]] = {}

    async def list(self, workspace_id: str) -> list[MapsFeedLayer]:
        return list(self._layers.get(workspace_id, {}).values())

    async def save(self, workspace_id: str, layer: MapsFeedLayer, *, user_id: str | None) -> None:
        self._layers.setdefault(workspace_id, {})[layer.id] = layer

    async def delete(self, workspace_id: str, layer_id: str) -> bool:
        return self._layers.get(workspace_id, {}).pop(layer_id, None) is not None
