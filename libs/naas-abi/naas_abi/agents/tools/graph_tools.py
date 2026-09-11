"""KnowledgeGraphAgent tools for the Nexus Knowledge Graph (NodeGraph).

Same data as ``/api/graph`` (``/list``, ``/kpis``, ``/overview``,
``/network/search``, ``/discovery/instance-detail``) and ``/api/view/list``,
with the same workspace membership check. Every graph argument is resolved
against ``list_graphs(workspace_id)`` first, so a tool can only read graphs
this workspace lists. There is deliberately no raw SPARQL tool: the triple
store is shared across tenants and a free-form query could read another
workspace's graphs.

The graph selected in the network view arrives as the open feature resource
(kind ``graph``, the graph id or URI), so tools default to it.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.feature.context import active_feature_resource_id
from naas_abi.agents.feature.runtime import (
    check_member,
    clip,
    guarded,
    jsonable,
    require_member,
    run,
    run_db,
    tool_context,
)

GRAPH_RESOURCE_KIND = "graph"
_FEATURE = "Knowledge Graph"
_MAX_NODES = 40


def _service() -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService
    from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry

    try:
        return ServiceRegistry.instance().graph
    except RuntimeError:
        return GraphService()


def _workspace_graphs(workspace_id: str) -> list[Any]:
    packs = run(_service().list_graphs(workspace_id=workspace_id))
    return [graph for pack in packs for graph in pack.graphs]


def _resolve_graph(graph: str, graphs: list[Any]) -> Any | dict[str, str]:
    wanted = (graph or "").strip() or active_feature_resource_id(GRAPH_RESOURCE_KIND)
    if not wanted:
        return {
            "error": "No graph is selected. Pass graph (see list_workspace_graphs)."
        }
    for candidate in graphs:
        if (
            wanted in (candidate.id, candidate.uri)
            or candidate.label.lower() == wanted.lower()
        ):
            return candidate
    return {
        "error": f"Graph not in this workspace: {wanted}. See list_workspace_graphs."
    }


def _node(node: Any) -> dict[str, Any]:
    return {"id": node.id, "label": node.label, "type": node.type}


def graph_tools() -> list[BaseTool]:
    @tool
    def list_workspace_graphs() -> Any:
        """List the knowledge graphs of this workspace, grouped by role.

        Rows: id, uri, label, role. Pass id, uri, or label as `graph` to the
        other tools.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        open_graph = active_feature_resource_id(GRAPH_RESOURCE_KIND)

        def _run() -> Any:
            role = check_member(user_id, workspace_id)
            if isinstance(role, dict):
                return role
            packs = run(_service().list_graphs(workspace_id=workspace_id))
            return {
                "open_graph": open_graph,
                "packs": [
                    {
                        "role": pack.role_label,
                        "graphs": [
                            {"id": g.id, "uri": g.uri, "label": g.label}
                            for g in pack.graphs
                        ],
                    }
                    for pack in packs
                ],
            }

        return guarded(_FEATURE, _run)

    @tool
    def get_graph_stats(graph: str = "") -> Any:
        """KPIs for a graph (classes, individuals, relations, properties) and
        the top classes by instance count. Omit graph to use the open one."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        wanted = graph

        def _run() -> Any:
            role = check_member(user_id, workspace_id)
            if isinstance(role, dict):
                return role
            target = _resolve_graph(wanted, _workspace_graphs(workspace_id))
            if isinstance(target, dict):
                return target
            service = _service()
            kpis = run(
                service.get_graph_kpis(workspace_id=workspace_id, graph_uri=target.uri)
            )
            overview = run(
                service.get_graph_overview(
                    workspace_id=workspace_id, graph_uri=target.uri, limit=200
                )
            )
            return {
                "graph": {"id": target.id, "uri": target.uri, "label": target.label},
                "kpis": jsonable(kpis),
                "instances_by_class": jsonable(overview.instances_by_class[:20]),
            }

        return guarded(_FEATURE, _run)

    @tool
    def search_graph(query: str, graph: str = "") -> Any:
        """Search individuals in a graph by label. Returns matching nodes
        (id, label, type) and how many edges connect them. Omit graph to use
        the open one."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        if not (query or "").strip():
            return {"error": "query is required."}
        wanted = graph

        def _run() -> Any:
            role = check_member(user_id, workspace_id)
            if isinstance(role, dict):
                return role
            target = _resolve_graph(wanted, _workspace_graphs(workspace_id))
            if isinstance(target, dict):
                return target
            network = run(
                _service().search_network(
                    workspace_id=workspace_id,
                    graph_uri=target.uri,
                    search_query=query.strip(),
                    limit=_MAX_NODES,
                )
            )
            return {
                "graph": target.label,
                "nodes": [_node(n) for n in network.nodes[:_MAX_NODES]],
                "edges": len(network.edges),
            }

        return guarded(_FEATURE, _run)

    @tool
    def describe_individual(instance_uri: str, graph: str = "") -> Any:
        """One individual: its class, data properties, and relations.

        instance_uri comes from search_graph node ids. Omit graph to use the
        open one.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        wanted = graph

        def _run() -> Any:
            role = check_member(user_id, workspace_id)
            if isinstance(role, dict):
                return role
            target = _resolve_graph(wanted, _workspace_graphs(workspace_id))
            if isinstance(target, dict):
                return target
            detail = run(
                _service().discover_instance_detail(
                    workspace_id=workspace_id,
                    graph_uris=[target.uri],
                    instance_uri=instance_uri.strip(),
                )
            )
            out = jsonable(detail)
            out["relations"] = out.get("relations", [])[:40]
            out["data_properties"] = out.get("data_properties", [])[:40]
            return out

        return guarded(_FEATURE, _run)

    @tool
    def list_graph_views() -> Any:
        """Saved graph views visible to the user in this workspace (id, name,
        folder, graphs)."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx

        async def _run(db: Any) -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.view.service import (
                ViewService,
            )

            role = await require_member(db, user_id, workspace_id)
            if isinstance(role, dict):
                return role
            views = await ViewService(db=db).list_views(workspace_id, user_id=user_id)
            return {
                "total": len(views),
                "views": [
                    {
                        key: clip(value, 200)
                        if isinstance(value, str)
                        else jsonable(value)
                        for key, value in view.items()
                        if key
                        in {
                            "id",
                            "name",
                            "path",
                            "description",
                            "graph_id",
                            "graph_uri",
                            "visibility",
                        }
                    }
                    for view in views[:60]
                ],
            }

        return guarded(_FEATURE, lambda: run_db(_run))

    return [
        list_workspace_graphs,
        get_graph_stats,
        search_graph,
        describe_individual,
        list_graph_views,
    ]
