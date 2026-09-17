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
_MAPS = f"{_WEB}/app/workspace/[workspaceId]/maps"

MAPS_CODE_MAP = f"""Web only (Maps has no FastAPI domain):
- {_MAPS}/page.tsx and {_MAPS}/[datasetId]/page.tsx: Maps library and one layer's canvas (/maps/<datasetId>).
- {_MAPS}/lib/datasets.ts: the layer catalog (MAPS_BUILTIN_DATASETS, categories Public / Private / Custom).
- {_WEB}/lib/maps-custom-datasets.ts: deployment layers from NEXT_PUBLIC_MAPS_CUSTOM_DATASETS.
- {_MAPS}/lib/leaflet-map.ts, leaflet-tiles.ts, maps-feed.ts, maps-route.ts, firms.ts: Leaflet setup, tiles, feed polling, routes, FIRMS wildfire WMS.
- {_MAPS}/components/maps-*.tsx: one component per layer (earthquakes, wildfires, flights, ais, iss, news, presence, ...), maps-library.tsx, maps-section.tsx.
- {_WEB}/app/api/maps/<feed>/route.ts and {_WEB}/app/api/maps/_lib.ts: Next.js route handlers that proxy public feeds (CORS, User-Agent, caching).
- {_WEB}/stores/maps.ts and {_WEB}/components/shell/sidebar/maps-section.tsx: category toggles and sidebar.
Agent: naas_abi/agents/MapsAgent.py and naas_abi/agents/tools/maps_tools.py."""

MAPS_CAPABILITIES = """- Open a map layer from the library: public situation-awareness feeds (earthquakes, wildfires, temperature, GDACS hazards, air quality, weather alerts, tropical storms, volcanoes, flights, ships, ISS, news, conflict), basemaps, and Private "presence" (the workspace's devices and infrastructure).
- Layers refresh from public feeds; some are proxied by Next.js routes under /api/maps/ for CORS and User-Agent rules.
- Custom layers are added per deployment with NEXT_PUBLIC_MAPS_CUSTOM_DATASETS (no code change upstream).
- Optional keys: FIRMS_MAP_KEY adds the NASA FIRMS 24h wildfire overlay.
- Feature flag `maps` (on for every role by default)."""

_HANDOFF_PHRASES = (
    "which map layers are available",
    "show earthquakes on the map",
    "how do maps work",
    "add a custom map layer",
    "quelles couches de carte",
    "affiche les séismes sur la carte",
    "comment fonctionnent les cartes",
)


class MapsAgent(IntentAgent):
    """Office agent for Nexus Maps (web-only feature).

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi MapsAgent
    """

    name: str = "Maps"
    description: str = (
        "Office agent for Nexus Maps. Lists the map layers and their feeds, "
        "explains each layer, custom layers, and required keys, and how Maps "
        "is built, from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = feature_system_prompt(
        name="Maps",
        class_name="MapsAgent",
        feature="Maps",
        role="You explain the map layers and how each one gets its data.",
        context=(
            "On a map you receive an open-feature block (feature: maps, and "
            "open_map_dataset_id when a layer is open). Maps lives entirely in "
            "the web app, so the code is your main source."
        ),
        tasks="""1. "What can I do here?": answer from <capabilities>, with the real catalog (list_map_layers).
2. "How is it built?" or "where does layer X get data?": read the layer component and its /api/maps route first, then explain with paths.
3. Adding a layer: explain NEXT_PUBLIC_MAPS_CUSTOM_DATASETS (read maps-custom-datasets.ts) or a new built-in (datasets.ts + component + route).""",
        capabilities=MAPS_CAPABILITIES,
        code_map=MAPS_CODE_MAP,
    )
    suggestions: list[dict] = [
        {"label": "What can you do?", "value": "Which map layers can I use?"},
        {
            "label": "How is it built?",
            "value": "Where does the earthquakes layer get its data? Read the code and cite files.",
        },
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        return feature_handoff_intents("Maps", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        from naas_abi.agents.tools.maps_tools import maps_tools
        from naas_abi.agents.tools.nexus_source_tools import nexus_source_tools

        return maps_tools() + nexus_source_tools()

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
    ) -> "MapsAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
