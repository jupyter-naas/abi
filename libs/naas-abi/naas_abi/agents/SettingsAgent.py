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

SETTINGS_CODE_MAP = f"""Web (workspace settings):
- {_WS}/settings/layout.tsx and settings/page.tsx: settings shell and general page.
- {_WS}/settings/members/page.tsx, theme/page.tsx, secrets/page.tsx, drives/page.tsx, models/page.tsx, servers/page.tsx, services/page.tsx, apps/page.tsx, export/page.tsx.
- {_WEB}/components/settings/secrets-panel.tsx, models-panel.tsx, servers-panel.tsx, integrations-panel.tsx, provider-form.tsx.
Web (organization):
- {_WS}/organization/page.tsx, users/page.tsx, admins/page.tsx, workspaces/page.tsx, branding/page.tsx, domains/page.tsx, billing/page.tsx.
- {_WS}/help/page.tsx: help (routed to the settings feature).
- {_WEB}/lib/feature-access.ts: FeatureKey, role baselines, which route needs which flag.
API:
- {_API}/services/workspaces/adapters/primary/workspaces__primary_adapter__FastAPI.py and services/workspaces/service.py: workspaces, members, roles, theme, effective feature_flags.
- {_API}/services/organizations/adapters/primary/organizations__primary_adapter__FastAPI.py and services/organizations/service.py: organizations, members, invites, branding, role feature overrides.
- {_API}/services/secrets/service.py and services/secrets/adapters/primary/secrets__primary_adapter__FastAPI.py: encrypted workspace secrets (values masked on read).
- {_API}/services/iam/service.py, authorization.py, IAM_SPEC.md: scopes and workspace access checks.
- {_API}/core/feature_flags.py: build_feature_flags (enabled catalog, role baseline, organization override, workspace override).
- naas_abi/__init__.py: FeatureFlagsConfig and WorkspaceSeedConfig (config.yaml nexus_config: feature_flags, organizations, workspaces, agents, apps, ontologies).
Agent: naas_abi/agents/SettingsAgent.py, naas_abi/agents/tools/settings_tools.py, naas_abi/agents/tools/nexus_admin_tools.py."""

SETTINGS_CAPABILITIES = """- Workspace settings: name and theme, members and roles (owner, admin, member, viewer), secrets, drives (platform and system drive access), models and inference servers, services, apps enablement, export.
- Organization settings: users, admins, workspaces, branding, domains, billing, and role-level feature overrides.
- Feature access: each section has a flag; the effective set is the enabled catalog, the role baseline, organization overrides, then workspace overrides from config.
- I can show this workspace's settings, your role and effective flags, secret names (never values), list organizations, workspaces, and members, invite or remove members, change roles, and update your profile (admin actions need owner or admin)."""

_HANDOFF_PHRASES = (
    "invite a member",
    "change a member role",
    "which features are enabled",
    "workspace settings",
    "is the api key configured",
    "invite un membre",
    "change le rôle",
    "quelles fonctionnalités sont activées",
    "paramètres de l'espace",
    "what is my role",
    "which features can i see",
    "quel est mon rôle",
    "quels sont mes droits",
)


class SettingsAgent(IntentAgent):
    """Office agent for Nexus Settings (workspace and organization admin).

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi SettingsAgent
    """

    name: str = "Settings"
    description: str = (
        "Office agent for Nexus Settings. Shows workspace settings, your role "
        "and feature flags, secret names, members and organizations; invites, "
        "removes, and re-roles members; and explains how settings, feature "
        "flags, and IAM are built, from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = feature_system_prompt(
        name="Settings",
        class_name="SettingsAgent",
        feature="Settings",
        role="You administer the workspace and organization and explain Nexus settings.",
        context=(
            "On a settings, organization, or help page you receive an "
            "open-feature block (feature: settings.workspace, "
            "settings.organization, or settings, and the route). The route tells "
            "you which settings page is open."
        ),
        tasks="""1. "What can I do here?": answer from <capabilities>, for the open settings page.
2. "How is it built?" or "why can't I see feature X?": read <code_map> files first (feature_flags.py, feature-access.ts), then explain with paths; use get_workspace_settings for the real flags.
3. Admin actions: use the member and workspace tools. They refuse when your role is not allowed; report that.
4. Secrets: list_workspace_secret_names only. Never show or ask for a secret value in chat.
5. "What is my role?", "what can I see or do here?": call get_workspace_settings. Its your_role and feature_flags are for the signed-in user. Never ask who the user is and never infer it from a member list.""",
        capabilities=SETTINGS_CAPABILITIES,
        code_map=SETTINGS_CODE_MAP,
        constraints="- Confirm the target email and role before inviting, removing, or re-roling a member.",
    )
    suggestions: list[dict] = [
        {"label": "What can you do?", "value": "What can I do in Settings?"},
        {
            "label": "Feature flags",
            "value": "Which features are enabled for me here, and how are feature flags computed? Cite files.",
        },
        {"label": "Members", "value": "List the members of this workspace."},
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        return feature_handoff_intents("Settings", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        from naas_abi.agents.tools.nexus_admin_tools import nexus_admin_tools
        from naas_abi.agents.tools.nexus_source_tools import nexus_source_tools
        from naas_abi.agents.tools.settings_tools import settings_tools

        return settings_tools() + nexus_admin_tools() + nexus_source_tools()

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
    ) -> "SettingsAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
