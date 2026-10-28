"""Secondary port: where a workspace's map layers are kept (hidden flags: settings)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.feed_layers__schema import (
    MapsFeedLayer,
)


class MapsFeedLayerStorePort(ABC):
    @abstractmethod
    async def list(self, workspace_id: str) -> list[MapsFeedLayer]:
        """Every layer stored for the workspace."""

    @abstractmethod
    async def save(self, workspace_id: str, layer: MapsFeedLayer, *, user_id: str | None) -> None:
        """Insert or replace the layer with the same id."""

    @abstractmethod
    async def delete(self, workspace_id: str, layer_id: str) -> bool:
        """Remove a layer. Returns False when nothing was stored."""
