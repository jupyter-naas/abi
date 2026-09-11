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
- {_API}/services/apps/adapters/primary/apps__primary_adapter__FastAPI.py: catalog discovery from <module>/apps/<name>/manifest.json (module_app_dir locates an app's folder), and routes GET /api/apps/, GET|POST /api/apps/{{workspace_id}}, GET|PATCH|DELETE /api/apps/{{workspace_id}}/{{app_id}}, POST /api/apps/access-token, POST /api/apps/sso-token.
- {_API}/services/apps/adapters/secondary/postgres.py and naas_abi/apps/nexus/apps/api/migrations/0028_add_app_configs.sql: app_configs table.
- {_API}/services/apps/app_html_access.py and pages_sso.py (with *_test.py): short-lived tokens for bundled HTML and Cloudflare Pages SSO.
- {_API}/main.py: serve_app_html mounts /app-html/{{path}} and its frame headers.
- {_API}/core/workspace_catalog_seed.py: workspace `apps:` seed and resolve_app_enabled (DB row, then seed, then off).
App builder (create and edit static apps, code | live preview | agent):
- {_WEB}/app/workspace/[workspaceId]/apps/p/[slug]/page.tsx: the editor page (file tree, Monaco, live preview, Save, Submit).
- {_WEB}/components/apps-builder/: app-preview-frame.tsx (sandboxed iframe on /app-preview/, error bridge), app-file-tree.tsx.
- {_WEB}/lib/app-projects.ts: /api/app-projects client, file tree, preview URL, isAppProjectWriteTool (mirrors APP_PROJECT_WRITE_TOOLS).
- {_WEB}/stores/app-projects.ts: refreshes the editor and the preview after my write tools.
- {_API}/services/apps/projects/port.py and service.py: projects, path rules, draft vs saved, check, submit.
- {_API}/services/apps/projects/adapters/secondary/: source_control.py (git branch apps/<workspace>/<slug>), object_storage.py (live draft), module_apps.py ("Edit" copies a module app), github.py (submit as a review branch).
- {_API}/services/apps/projects/adapters/primary/app_projects__primary_adapter__FastAPI.py: /api/app-projects routes and the /app-preview/<token>/<path> preview (CSP sandbox, no session).
- {_API}/services/apps/projects/preview_token.py: preview tokens that are never session tokens.
Agent: naas_abi/agents/AppsAgent.py, naas_abi/agents/tools/apps_tools.py and app_builder_tools.py (this agent)."""

APPS_CAPABILITIES = """- Browse the workspace's apps as a database (gallery, table, list, board views with filters, sort, group, search). Module apps and tenant external shortcuts appear together.
- Open an app: bundled HTML apps embed same-origin through /app-html/ with a short-lived access token; external apps embed directly, with a Pages SSO token when the host needs one. The metadata panel is opt-in.
- Enable or disable module apps per workspace (Settings > Apps, or ask me). Only enabled apps show on the Apps page. Missing rows default to off unless the workspace seed lists the app.
- Ship a new app: add <module>/apps/<name>/manifest.json (plus HTML/assets) inside a loaded module; the catalog is cached per process, so restart the API.
- Build a new app in Nexus: "New app" (or ask me) creates a project from a static starter; the editor shows the code on the left, the app live in the middle, and me on the right. Every edit, mine or yours, shows up in the preview at once.
- Edit an existing module app: "Edit" duplicates it into a project; the original stays unchanged until the tech team merges the change.
- Save commits the project (history in git); Submit sends it to the source repository as a new branch for the tech team to review (when submitting is configured).
- The Apps feature flag is `apps` (on for owners and admins by default, off for members and viewers unless the workspace enables it)."""

_HANDOFF_PHRASES = (
    "create an app",
    "build an app",
    "make me an app",
    "edit this app",
    "change this app",
    "crée une app",
    "créer une application",
    "construis une app",
    "modifie cette app",
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

    Lists, opens, enables and disables the workspace's apps, builds and edits
    static apps in the Apps editor, and explains how Apps is built from the
    code (read_nexus_source), not from memory.

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi AppsAgent
    """

    name: str = "Apps"
    description: str = (
        "Office agent for Nexus Apps. Lists, opens, enables and disables the "
        "workspace's apps, creates and edits static apps in the Apps editor, "
        "and explains how Apps works (manifest discovery, per-workspace enable "
        "state, HTML embed tokens, Pages SSO) from the code."
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
In the app editor the block names open_app_project_id instead: the builder tools default to that project, and preview_error lines are runtime errors the live preview just reported.
{roster_line("AppsAgent")}
</context>

<tasks>
1. "What can I do here?": answer from <capabilities>, then tie it to the open app or the workspace's apps (list_workspace_apps).
2. "How is this built / how does X work?": read the files in <code_map> first (read_nexus_source, search_nexus_source), then explain with paths.
3. Operating: get_app for details, set_app_enabled to enable or disable. Report the tool result.
4. Errors (app will not open, blocked iframe, 401 on /app-html/, missing app): read the matching code path, then explain the cause and the fix.
5. Building: create_app_project for a new app, edit_module_app to change an existing module app (never edit it in place), then follow <app_building>.
</tasks>

<app_building>
- Apps are static: manifest.json plus HTML, CSS and JavaScript. No build step, no npm, nothing that needs a compiler. Libraries load from a CDN (https://cdn.jsdelivr.net/npm/...) or from files in the app.
- Read before you edit: list_app_files, then read_app_file on the files you change. Never guess a file's content.
- index.html holds the structure, styles.css the look, app.js the behaviour; split a bigger app into js/*.js. Links between files are relative (styles.css, js/chart.js), never absolute (/x) and never outside the app (../).
- Keep manifest.json valid: "name", "description", "url": "html:index.html", "icon_emoji".
- write_app_file for new or small files; replace_in_app_file for a small change in a large file.
- The preview is sandboxed: no cookies, no calls to Nexus, storage lives in memory only. Fetch public URLs or JSON files shipped in the app.
- After writing, call check_app and fix every error and preview_error before you say it works.
- Edits are live but unsaved. Save (save_app_project) when the user asks; otherwise tell them to Save. Submit (submit_app_project) only when the user asks: it opens a review branch, nothing goes live until the tech team merges it.
- Never put secrets, keys or tokens in app files.
</app_building>

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
        """Apps and app builder tools, plus read-only Nexus source tools."""
        from naas_abi.agents.tools.app_builder_tools import app_builder_tools
        from naas_abi.agents.tools.apps_tools import apps_tools
        from naas_abi.agents.tools.nexus_source_tools import nexus_source_tools

        return apps_tools() + app_builder_tools() + nexus_source_tools()

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
