"""Compatibility layer for graph exports.

Deprecated: import graph router and schemas from
`naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary`.
"""

from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary import (
    GraphClear,
    GraphCreate,
    GraphData,
    GraphDelete,
    GraphEdge,
    GraphInfo,
    GraphNode,
    GraphOverview,
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService

# Deprecated aliases kept for migration clarity.
DeprecatedGraphCreate = GraphCreate
DeprecatedGraphClear = GraphClear
DeprecatedGraphData = GraphData
DeprecatedGraphDelete = GraphDelete
DeprecatedGraphEdge = GraphEdge
DeprecatedGraphInfo = GraphInfo
DeprecatedGraphNode = GraphNode
DeprecatedGraphOverview = GraphOverview
DeprecatedGraphRouter = router
DeprecatedGraphService = GraphService

__all__ = [
    "DeprecatedGraphCreate",
    "DeprecatedGraphClear",
    "DeprecatedGraphData",
    "DeprecatedGraphDelete",
    "DeprecatedGraphEdge",
    "DeprecatedGraphInfo",
    "DeprecatedGraphNode",
    "DeprecatedGraphOverview",
    "DeprecatedGraphRouter",
    "DeprecatedGraphService",
    "GraphCreate",
    "GraphClear",
    "GraphData",
    "GraphDelete",
    "GraphEdge",
    "GraphInfo",
    "GraphNode",
    "GraphOverview",
    "GraphService",
    "router",
]
