from typing import TYPE_CHECKING, Any

from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphEdgeData,
    GraphInfoData,
    GraphNetworkData,
    GraphNodeData,
    GraphOverviewData,
    GraphProtectedError,
    GraphServiceUnavailableError,
)

if TYPE_CHECKING:
    from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService

__all__ = [
    "GraphEdgeData",
    "GraphInfoData",
    "GraphNetworkData",
    "GraphNodeData",
    "GraphOverviewData",
    "GraphProtectedError",
    "GraphService",
    "GraphServiceUnavailableError",
]


def __getattr__(name: str) -> Any:
    """Lazily expose ``GraphService`` without importing ``service`` at package import.

    ``service`` computes a module-level constant from ``ABIModule.get_instance()``, so
    eagerly importing it here forced the whole app to be initialized just to import the
    package — breaking pure/co-located tests under ``graph/`` (e.g. ``query/``). Resolve
    it on first attribute access instead; ``from ...graph import GraphService`` still works.
    """
    if name == "GraphService":
        from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService

        return GraphService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
