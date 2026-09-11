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

MARKETPLACE_CODE_MAP = f"""Web:
- {_WEB}/app/workspace/[workspaceId]/marketplace/page.tsx: Marketplace page (catalog grid, filters, module detail panel, pricing).
- {_WEB}/components/shell/sidebar/marketplace-section.tsx: Marketplace sidebar section.
API:
- {_API}/services/modules/handlers.py: GET /api/modules/ (installed + catalog) and GET /api/modules/config (pricing, tiers).
- {_API}/services/modules/service.py: ModulesService.list_modules, filesystem catalog scan (_build_catalog), agent metadata extraction.
- {_API}/services/modules/schema.py: ModuleInfo, ModulesResponse, MarketplaceConfigResponse.
- {_API}/core/config.py: MarketplaceConfig (pricing and usage tiers from nexus_config).
Engine: naas_abi_core/module/Module.py (BaseModule) and naas_abi_core/engine/Engine.py (which modules load, from config.yaml modules:).
Agent: naas_abi/agents/MarketplaceAgent.py and naas_abi/agents/tools/marketplace_tools.py."""

MARKETPLACE_CAPABILITIES = """- Discover ABI modules: the catalog lists every module found on disk (core, ai, application, domain) and flags the ones the engine loaded (installed).
- Inspect a module: description, tier (community or enterprise), maintainer, its agent, app URL, whether a demo login exists.
- Pricing: usage tiers and model token costs from the marketplace config.
- Install or remove a module: add or remove it under modules: in config.yaml (enabled: true), then restart the API. There is no install button that changes the running engine.
- Marketplace (modules) is not Apps: Apps are launchable web apps (apps/<name>/manifest.json) inside loaded modules, enabled per workspace.
- Feature flag `marketplace` (owners and admins by default)."""

_HANDOFF_PHRASES = (
    "install a module",
    "which modules are available",
    "browse the marketplace",
    "what is in the marketplace",
    "module pricing",
    "installer un module",
    "quels modules sont disponibles",
    "parcourir la marketplace",
    "tarifs des modules",
)


class MarketplaceAgent(IntentAgent):
    """Office agent for Nexus Marketplace (ABI modules catalog).

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi MarketplaceAgent
    """

    name: str = "Marketplace"
    description: str = (
        "Office agent for Nexus Marketplace. Lists and explains ABI modules "
        "(installed and available), their tiers and pricing, how to install "
        "one, and how the Marketplace is built, from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = feature_system_prompt(
        name="Marketplace",
        class_name="MarketplaceAgent",
        feature="Marketplace",
        role="You explain and inspect the ABI modules catalog.",
        context=(
            "On the Marketplace page you receive an open-feature block (feature: "
            "marketplace, and open_module_id when a module detail is open). Tools "
            "default to that module."
        ),
        tasks="""1. "What can I do here?": answer from <capabilities>, then show real modules (list_marketplace_modules).
2. "How is it built?": read <code_map> files first, then explain with paths.
3. A module question: get_marketplace_module. Pricing: get_marketplace_pricing.
4. "Install X": check it with get_marketplace_module, then give the exact config.yaml change. Say it needs an API restart and an operator with config access.""",
        capabilities=MARKETPLACE_CAPABILITIES,
        code_map=MARKETPLACE_CODE_MAP,
        constraints="- Never claim a module was installed; installation is a config change plus restart.",
    )
    suggestions: list[dict] = [
        {"label": "What can you do?", "value": "What can I do in the Marketplace?"},
        {
            "label": "How is it built?",
            "value": "How is the Marketplace catalog built? Read the code and cite files.",
        },
        {"label": "Installed modules", "value": "Which modules are installed here?"},
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        return feature_handoff_intents("Marketplace", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        from naas_abi.agents.tools.marketplace_tools import marketplace_tools
        from naas_abi.agents.tools.nexus_source_tools import nexus_source_tools

        return marketplace_tools() + nexus_source_tools()

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
    ) -> "MarketplaceAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
