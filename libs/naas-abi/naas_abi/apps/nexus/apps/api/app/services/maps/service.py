"""Module-registered map projections, authorized by the workspace graph scope."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope


class GraphQueryPort(Protocol):
    def query(self, query: str) -> Any: ...


_LAYER_COLOR = re.compile(r"^#[0-9a-fA-F]{3,8}$")


@dataclass(frozen=True)
class GraphMapLayer:
    id: str
    title: str
    description: str
    graph_uri: str
    feed: Callable[[GraphQueryPort], dict]
    icon: str = "MapPin"
    # Optional #rgb / #rrggbb pin and cluster color. The web honors this
    # (and each pin's color) instead of hashing a palette color.
    color: str | None = None


class MapsCatalog:
    def __init__(self):
        self.layers: dict[str, GraphMapLayer] = {}

    def register(self, layer: GraphMapLayer) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", layer.id):
            raise ValueError("Map layer ID must be route-safe")
        if layer.color is not None and not _LAYER_COLOR.fullmatch(layer.color):
            raise ValueError("Map layer color must be a #rgb or #rrggbb hex value")
        if layer.id in self.layers:
            raise ValueError("Map layer already registered: " + layer.id)
        self.layers[layer.id] = layer

    def list_layers(self, scope: GraphAccessScope) -> list[dict]:
        listed: list[dict] = []
        for n, layer in enumerate(self.layers.values()):
            if layer.graph_uri not in scope.readable:
                continue
            item: dict = {
                "id": layer.id,
                "title": layer.title,
                "description": layer.description,
                "icon": layer.icon,
                "graphUri": layer.graph_uri,
                "group": "Custom",
                "order": n,
                "runtime": True,
            }
            if layer.color:
                item["color"] = layer.color
            listed.append(item)
        return listed

    def feed(self, layer_id: str, scope: GraphAccessScope, store: GraphQueryPort) -> dict:
        layer = self.layers[layer_id]
        scope.require(scope.workspace_id, [layer.graph_uri])
        return layer.feed(store)
