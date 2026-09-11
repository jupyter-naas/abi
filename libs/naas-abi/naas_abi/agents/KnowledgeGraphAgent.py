from naas_abi.agents.feature import (
    FEATURE_RECURSION_LIMIT,
    build_feature_agent,
    configured_feature_model,
    feature_handoff_intents,
    feature_system_prompt,
)
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
)

_WEB = "naas_abi/apps/nexus/apps/web/src"
_API = "naas_abi/apps/nexus/apps/api/app"

GRAPH_CODE_MAP = f"""Web:
- {_WEB}/app/workspace/[workspaceId]/graph/network/page.tsx: NodeGraph network view (vis-network), graph picker, search, inspector.
- {_WEB}/app/workspace/[workspaceId]/graph/explore/page.tsx and explore-next/page.tsx: table-style exploration (classes, columns, drill-down).
- {_WEB}/app/workspace/[workspaceId]/graph/individuals/page.tsx, create-graph/page.tsx, create-individual/page.tsx, import/page.tsx, export/page.tsx.
- {_WEB}/components/graph/vis-network.tsx, instance-inspector.tsx, graph-node-table.tsx: network canvas, node inspector, node table.
- {_WEB}/lib/graph-query/explore-state.ts, columns.ts, filters.ts, paths.ts: exploration query state.
- {_WEB}/lib/triples-export.ts and {_WEB}/stores/graph-export.ts: Turtle export and export toasts.
- {_WEB}/stores/knowledge-graph.ts: selected graph, visible graphs, nodes, cache refresh.
- {_WEB}/components/shell/sidebar/knowledge-graph-section.tsx: graphs and saved views sidebar.
API:
- {_API}/services/graph/adapters/primary/graph__primary_adapter__FastAPI.py: /api/graph routes (list, create, update, clear, delete, nodes and properties, overview, kpis, network, search, export, analyze, import, discovery/*).
- {_API}/services/graph/service.py: GraphService (list_graphs per workspace, KPIs cache, network, search, discovery, import/export).
- {_API}/services/graph/graph__schema.py: GraphInfoData, GraphKpisData, GraphNetworkData, discovery dataclasses.
- {_API}/services/graph/query/compiler.py, sparql_safe.py, guards.py: exploration query compiler and SPARQL safety guards.
- {_API}/services/graph/discovery_triples_export.py: triples export for discovery selections.
- {_API}/services/view/service.py and {_API}/api/endpoints/view.py: saved graph views (/api/view).
Engine: naas_abi_core/services/triple_store/ (TripleStoreService, TripleStorePorts, adaptors for Fuseki, Oxigraph, filesystem).
Agent: naas_abi/agents/KnowledgeGraphAgent.py and naas_abi/agents/tools/graph_tools.py."""

GRAPH_CAPABILITIES = """- Pick one or more knowledge graphs of the workspace and see them as a network (NodeGraph), a table (Explore), or a list of individuals.
- Search individuals, inspect one (class, data properties, relations), follow relations.
- Create a graph, create individuals, add or edit data and object properties; clear or delete a graph.
- Import a file into a graph (analyze first), export a graph or a selection as Turtle.
- Save views (graph + filters) in folders and reopen them from the sidebar.
- Feature flag `graph` (owners and admins by default). Every graph is scoped to the workspace."""

_HANDOFF_PHRASES = (
    "show my knowledge graph",
    "search the knowledge graph",
    "how many individuals in the graph",
    "export the graph",
    "import data into the graph",
    "explore the nodegraph",
    "montre mon graphe de connaissances",
    "cherche dans le graphe",
    "combien d'individus dans le graphe",
    "exporter le graphe",
)


class KnowledgeGraphAgent(IntentAgent):
    """Office agent for the Nexus Knowledge Graph (NodeGraph).

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi KnowledgeGraphAgent
    """

    name: str = "Knowledge Graph"
    description: str = (
        "Office agent for the Nexus Knowledge Graph (NodeGraph). Lists the "
        "workspace's graphs, their KPIs and top classes, searches and inspects "
        "individuals, lists saved views, and explains how the graph UI and API "
        "are built, from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = feature_system_prompt(
        name="Knowledge Graph",
        class_name="KnowledgeGraphAgent",
        feature="Knowledge Graph",
        role="You read the workspace's knowledge graphs and explain the NodeGraph UI.",
        context=(
            "On a graph page you receive an open-feature block (feature: graph, "
            "the route, and open_graph_id when a graph is selected). Tools "
            "default to that graph. You only see graphs this workspace lists."
        ),
        tasks="""1. "What can I do here?": answer from <capabilities>, tied to the real graphs (list_workspace_graphs).
2. "How is it built?": read <code_map> files first, then explain with paths.
3. Data questions: get_graph_stats, search_graph, describe_individual, list_graph_views.
4. Writes (create graph or individual, import, clear, delete): explain the UI flow and route; you have no write tools.""",
        capabilities=GRAPH_CAPABILITIES,
        code_map=GRAPH_CODE_MAP,
        constraints=(
            "- Never run or suggest cross-workspace SPARQL; the triple store is shared.\n"
            "- Never claim a graph changed: you have no write tools."
        ),
    )
    suggestions: list[dict] = [
        {
            "label": "What can you do?",
            "value": "What can I do with the knowledge graph?",
        },
        {
            "label": "How is it built?",
            "value": "How is the NodeGraph network view implemented? Read the code and cite files.",
        },
        {"label": "This graph", "value": "Give me the stats of the open graph."},
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        return feature_handoff_intents("Knowledge Graph", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        from naas_abi.agents.tools.graph_tools import graph_tools
        from naas_abi.agents.tools.nexus_source_tools import nexus_source_tools

        return graph_tools() + nexus_source_tools()

    @classmethod
    def get_chat_model_id(cls) -> str:
        return configured_feature_model()

    @classmethod
    def get_chat_model_ids(cls) -> list[str]:
        return [configured_feature_model()]

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
        model_id: str | None = None,
    ) -> "KnowledgeGraphAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
