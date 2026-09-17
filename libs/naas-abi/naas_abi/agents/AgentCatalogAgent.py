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
_WS = f"{_WEB}/app/workspace/[workspaceId]"

CATALOG_CODE_MAP = f"""Web:
- {_WS}/settings/agents/page.tsx and settings/agents/[agentId]/page.tsx: roster list, enable/disable, default agent, agent detail (model, prompt, suggestions).
- {_WEB}/stores/agents.ts: agents fetch and sync, default and pane agent selection.
- {_WEB}/app/workspace/[workspaceId]/chat/components/chat-agent-selector.tsx: the agent picker in chat and the right pane.
- {_WEB}/lib/pick-workspace-default-agent.ts and {_WEB}/lib/feature-office-agents.ts: which agent the pane binds per section.
API:
- {_API}/services/agents/adapters/primary/agents__primary_adapter__FastAPI.py: /api/agents (list, sync, create, update, delete) and the roster sync from config (_workspace_agent_roster, pick_workspace_chat_agent_id).
- {_API}/services/agents/service.py, port.py, adapters/secondary/postgres.py: AgentService and AgentRecord.
- {_API}/core/workspace_catalog_seed.py: parse_agent_ref and workspace seeds (default_agent, agents).
Engine: naas_abi_core/module/ModuleAgentLoader.py (how agent classes are discovered from <module>/agents/*.py).
Agent: naas_abi/agents/AgentCatalogAgent.py and naas_abi/agents/tools/agent_catalog_tools.py."""

CATALOG_CAPABILITIES = """- See the workspace's agent roster: which agents are enabled, which one is the default (main chat orchestrator), their models.
- Open an agent: description, suggestions, intents, prompt preview; enable or disable it; pick its model.
- Roster comes from config: a workspace's agents: list in config.yaml ("<module> <ClassName>") and default_agent. Unlisted agents stay off.
- Skills (reusable /slug prompts) belong to the Skills office agent: it writes and saves them, Settings > Skills edits them by hand. Point the user there; you have no skill tools.
- The Agents feature flag is `agents` (owners and admins by default)."""

_HANDOFF_PHRASES = (
    "which agents are available",
    "add an agent to the workspace",
    "what is the default agent",
    "which agent answers here",
    "quels agents sont disponibles",
    "ajouter un agent à l'espace",
    "quel est l'agent par défaut",
)


class AgentCatalogAgent(IntentAgent):
    """Office agent for Settings > Agents (skills belong to SkillsAgent).

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi AgentCatalogAgent
    """

    name: str = "Agent Catalog"
    description: str = (
        "Office agent for the Nexus agent catalog. Lists the workspace's "
        "agents and the agent classes a roster can add, and explains rosters, "
        "defaults, and how they are built, from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = feature_system_prompt(
        name="Agent Catalog",
        class_name="AgentCatalogAgent",
        feature="Agents",
        role="You explain and inspect the workspace's agent roster.",
        context=(
            "On Settings > Agents you receive an open-feature block (feature: "
            "agents, and the open agent as the feature resource on a detail "
            "page). Tools default to it."
        ),
        tasks="""1. "What can I do here?": answer from <capabilities>, tied to the real roster (list_workspace_agents).
2. "How is it built?": read <code_map> files first, then explain with paths.
3. "Add agent X": find its roster ref with list_agent_classes, then give the exact config.yaml change (agents: list) and say a restart syncs it.
4. Skills: not yours. Say the Skills agent writes and saves them (or Settings > Skills), and let Abi hand the request over.""",
        capabilities=CATALOG_CAPABILITIES,
        code_map=CATALOG_CODE_MAP,
        constraints="- Never claim you enabled an agent: you have no write tools, and skills are the Skills agent's to create.",
    )
    suggestions: list[dict] = [
        {"label": "What can you do?", "value": "What can I do with the agent roster?"},
        {
            "label": "How is it built?",
            "value": "How does a workspace roster decide which agents are enabled? Cite files.",
        },
        {"label": "Roster", "value": "Which agents are on this workspace?"},
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        return feature_handoff_intents("Agent Catalog", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        from naas_abi.agents.tools.agent_catalog_tools import agent_catalog_tools
        from naas_abi.agents.tools.nexus_source_tools import nexus_source_tools

        return agent_catalog_tools() + nexus_source_tools()

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
    ) -> "AgentCatalogAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
