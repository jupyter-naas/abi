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

SEARCH_CODE_MAP = f"""Web:
- {_WEB}/app/workspace/[workspaceId]/search/page.tsx: Search page (query box, source buckets Public / Private / Custom, results).
- {_WEB}/stores/search.ts: fans out to POST /api/search/web, POST /api/search/private, and custom source endpoints configured per tenant.
- {_WEB}/components/shell/sidebar/search-section.tsx: Search sidebar (sources).
API:
- {_API}/services/search/adapters/primary/search__primary_adapter__FastAPI.py: POST /api/search/ (workspace search), /web, /private, GET /suggestions.
- {_API}/services/search/service.py (and service_test.py): SearchService.search (a stub: returns no results), web_search (Wikipedia, DuckDuckGo), private_search (source ontology), get_suggestions (Wikipedia opensearch).
- {_API}/services/search/search__schema.py: request and result dataclasses.
Agent: naas_abi/agents/SearchAgent.py and naas_abi/agents/tools/search_tools.py."""

SEARCH_CAPABILITIES = """- Search public sources (Wikipedia or DuckDuckGo) from the Search page, with suggestions as you type.
- Search private sources: today that is the loaded ontologies (classes and properties by label).
- Custom sources: endpoints a deployment configures for the tenant; the browser calls them directly.
- Workspace-wide search (files, chats, graph) is not implemented yet: POST /api/search/ is a stub that returns no results.
- Feature flag `search` (owners and admins by default)."""

_HANDOFF_PHRASES = (
    "search the web",
    "search wikipedia",
    "why does search return nothing",
    "how does nexus search work",
    "cherche sur le web",
    "recherche wikipedia",
    "pourquoi la recherche ne renvoie rien",
)


class SearchAgent(IntentAgent):
    """Office agent for Nexus Search.

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi SearchAgent
    """

    name: str = "Search"
    description: str = (
        "Office agent for Nexus Search. Runs the same public (Wikipedia, "
        "DuckDuckGo) and private (ontology) searches as the Search page and "
        "explains what Search covers and how it is built, from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = feature_system_prompt(
        name="Search",
        class_name="SearchAgent",
        feature="Search",
        role="You run the Search page's searches and explain what Search covers.",
        context="On the Search page you receive an open-feature block (feature: search).",
        tasks="""1. "What can I do here?": answer from <capabilities>, including what is not implemented.
2. "How is it built?" or "why no results?": read <code_map> files first (SearchService), then explain with paths.
3. Searching: search_public_web or search_ontology_terms, then report the results with their sources.""",
        capabilities=SEARCH_CAPABILITIES,
        code_map=SEARCH_CODE_MAP,
    )
    suggestions: list[dict] = [
        {"label": "What can you do?", "value": "What can I search here?"},
        {
            "label": "How is it built?",
            "value": "How does Nexus Search work? Read the code and cite files.",
        },
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        return feature_handoff_intents("Search", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        from naas_abi.agents.tools.nexus_source_tools import nexus_source_tools
        from naas_abi.agents.tools.search_tools import search_tools

        return search_tools() + nexus_source_tools()

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
    ) -> "SearchAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
