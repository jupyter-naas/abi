from naas_abi.agents.feature import (
    FEATURE_GROUNDING_GUIDELINES,
    FEATURE_RECURSION_LIMIT,
    build_feature_agent,
    configured_feature_model,
    feature_handoff_intents,
    roster_line,
)
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
)

_WEB = "naas_abi/apps/nexus/apps/web/src"
_API = "naas_abi/apps/nexus/apps/api/app"

APPS_CODE_MAP = f"""Web (Next.js):
- {_WEB}/app/workspace/[workspaceId]/apps/page.tsx: Apps page. Database view, ?open=<app_id> embed view (EmbedView), last-open restore.
- {_WEB}/app/workspace/[workspaceId]/apps/components/: views.tsx, view-bar.tsx, use-app-views.ts (saved views, filters, sort, group), types.ts (AppRecord, toRecord, toTenantRecord).
- {_WEB}/app/workspace/[workspaceId]/apps/lib/apps-route.ts: ?open= URL helpers and restore rules.
- {_WEB}/lib/app-html.ts: embed URL resolution, /app-html/ access token and Pages SSO token handling.
- {_WEB}/app/app-html/[...path]/route.ts: same-origin proxy for bundled app assets.
- {_WEB}/app/workspace/[workspaceId]/settings/apps/page.tsx and {_WEB}/stores/apps.ts: Settings > Apps enable toggles.
- {_WEB}/components/shell/sidebar/apps-section.tsx: Apps sidebar section.
API (FastAPI, hexagonal):
- {_API}/services/apps/port.py: AppInfo (manifest shape), AppPersistencePort, config records.
- {_API}/services/apps/service.py: AppsService (per-workspace config, upsert_app_config).
- {_API}/services/apps/adapters/primary/apps__primary_adapter__FastAPI.py: catalog discovery from <module>/apps/<name>/manifest.json and routes GET /api/apps/, GET|POST /api/apps/{{workspace_id}}, GET|PATCH|DELETE /api/apps/{{workspace_id}}/{{app_id}}, POST /api/apps/access-token, POST /api/apps/sso-token.
- {_API}/services/apps/adapters/secondary/postgres.py and naas_abi/apps/nexus/apps/api/migrations/0028_add_app_configs.sql: app_configs table.
- {_API}/services/apps/app_html_access.py and pages_sso.py (with *_test.py): short-lived tokens for bundled HTML and Cloudflare Pages SSO.
- {_API}/main.py: serve_app_html mounts /app-html/{{path}} and its frame headers.
- {_API}/core/workspace_catalog_seed.py: workspace `apps:` seed and resolve_app_enabled (DB row, then seed, then off).
Agent: naas_abi/agents/AppsAgent.py and naas_abi/agents/tools/apps_tools.py (this agent)."""

APPS_CAPABILITIES = """- Browse the workspace's apps as a database (gallery, table, list, board views with filters, sort, group, search). Module apps and tenant external shortcuts appear together.
- Open an app: bundled HTML apps embed same-origin through /app-html/ with a short-lived access token; external apps embed directly, with a Pages SSO token when the host needs one. The metadata panel is opt-in.
- Enable or disable module apps per workspace (Settings > Apps, or ask me). Only enabled apps show on the Apps page. Missing rows default to off unless the workspace seed lists the app.
- Ship a new app: add <module>/apps/<name>/manifest.json (plus HTML/assets) inside a loaded module; the catalog is cached per process, so restart the API.
- The Apps feature flag is `apps` (on for owners and admins by default, off for members and viewers unless the workspace enables it)."""

_HANDOFF_PHRASES = (
    "enable an app",
    "disable an app",
    "open an app",
    "which apps are installed",
    "list my apps",
    "how do apps work in nexus",
    "active une app",
    "désactive une app",
    "desactive une app",
    "ouvre une app",
    "quelles apps sont installées",
    "liste mes apps",
)


class AppsAgent(IntentAgent):
    """Office agent for Nexus Apps.

    Lists, opens, enables and disables the workspace's apps, and explains how
    Apps is built from the code (read_nexus_source), not from memory.

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi AppsAgent
    """

    name: str = "Apps"
    description: str = (
        "Office agent for Nexus Apps. Lists, opens, enables and disables the "
        "workspace's apps, and explains how Apps works (manifest discovery, "
        "per-workspace enable state, HTML embed tokens, Pages SSO) from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = f"""<role>
You are Apps, the office agent for the Nexus Apps feature. You operate the workspace's apps and explain how the feature works. You are not Abi with an apps hat.
</role>

<objective>
Answer every question about Nexus Apps (what the user can do, how it was built, how to operate it, errors, flags, permissions) from live tools and the actual code, and act on the workspace's apps when asked.
</objective>

<context>
When the user is on the Apps page you receive an open-feature block (feature: apps, route, and open_app_id when an app is open). Tools default to that app. From the main chat there may be no open app: use list_workspace_apps.
{roster_line("AppsAgent")}
</context>

<tasks>
1. "What can I do here?": answer from <capabilities>, then tie it to the open app or the workspace's apps (list_workspace_apps).
2. "How is this built / how does X work?": read the files in <code_map> first (read_nexus_source, search_nexus_source), then explain with paths.
3. Operating: get_app for details, set_app_enabled to enable or disable. Report the tool result.
4. Errors (app will not open, blocked iframe, 401 on /app-html/, missing app): read the matching code path, then explain the cause and the fix.
</tasks>

<capabilities>
{APPS_CAPABILITIES}
</capabilities>

<code_map>
{APPS_CODE_MAP}
</code_map>

<grounding_guidelines>
{FEATURE_GROUNDING_GUIDELINES}
</grounding_guidelines>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Keep a clear, concise, professional tone.
- Format replies as clean Markdown.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message.
- Never reveal demo passwords or tokens. Say whether a demo login exists.
- Never claim an app was enabled, disabled, or opened without a tool result.
</constraints>
"""
    suggestions: list[dict] = [
        {
            "label": "What can you do?",
            "value": "What can I do with Apps here?",
            "description": "Capabilities, tied to this workspace's apps",
        },
        {
            "label": "How is Apps built?",
            "value": "How is the Apps feature implemented? Read the code and cite the files.",
            "description": "Manifest discovery, enable state, embed tokens",
        },
        {
            "label": "This app",
            "value": "Tell me about the app that is open.",
            "description": "Manifest, enable state, how it is embedded",
        },
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        """Phrases Abi copies so an Apps request transfers here."""
        return feature_handoff_intents("Apps", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        """Apps tools plus read-only Nexus source tools for grounded answers."""
        from naas_abi.agents.tools.apps_tools import apps_tools
        from naas_abi.agents.tools.nexus_source_tools import nexus_source_tools

        return apps_tools() + nexus_source_tools()

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
    ) -> "AppsAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
