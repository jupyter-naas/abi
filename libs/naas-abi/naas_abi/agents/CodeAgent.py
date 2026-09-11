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
_CODE = f"{_WEB}/app/workspace/[workspaceId]/code"

CODE_CODE_MAP = f"""Web:
- {_CODE}/layout.tsx, page.tsx, repos/page.tsx, new/page.tsx: Code home, repo list, new repo.
- {_CODE}/r/[owner]/[repo]/page.tsx and layout.tsx: one repo (files, README); sibling folders branches/, commits/, pulls/ (with pulls/[number]/), actions/, workspaces/.
- {_CODE}/branches/page.tsx, pulls/page.tsx, workspaces/page.tsx: cross-repo branches, pull requests, coding workspaces.
- {_WEB}/app/workspace/[workspaceId]/ide/page.tsx and lab/page.tsx: embedded IDE (code-server) and lab; both map to the `code` feature.
- {_WEB}/stores/code.ts and {_WEB}/stores/platform-status.ts: selected repo, active branch, Coder runtime binding shown in the footer.
- {_WEB}/components/shell/sidebar/code-section.tsx: Code sidebar.
API:
- {_API}/services/coding_environment/adapters/primary/coding_environment__primary_adapter__FastAPI.py: /api/coding-environments (repos, repo-contents, repo-file, repo-commits, branches, git-token, sandbox/runtime, environment start/stop/logs/access) and lookup_code_bindings for chat.
- {_API}/services/code_review/adapters/primary/code_review__primary_adapter__FastAPI.py: /api/code-review (pull requests, diffs, comments, reviews).
- {_API}/services/chat/adapters/primary/chat__primary_adapter__streaming.py: binds context.coding (repo, branch, sidecar, OpenCode harness) for a chat turn.
Engine:
- naas_abi_core/services/source_control/ (SourceControlPorts, SourceControlService; Forgejo and local_git adapters under adapters/secondary/).
- naas_abi_core/services/coding_environment/ (CodingEnvironmentPorts, CodingEnvironmentService; Coder and local_directory adapters under adapters/secondary/).
Related: naas_abi/agents/CodingAgent.py (OpenCode Coding agent) and naas_abi/agents/tools/coding_tools.py (sandbox file and terminal tools).
Agent: naas_abi/agents/CodeAgent.py and naas_abi/agents/tools/code_tools.py."""

CODE_CAPABILITIES = """- Browse repositories, files, commits, branches, pull requests, and CI runs (Actions); create a repo or a branch.
- Open a coding workspace (Coder container with a code-server IDE and an exec sidecar) on a repo and branch; start, stop, see logs.
- Review pull requests: diffs, comments, reviews.
- With a repo open, I can read, write, and list files in its sandbox checkout, run commands there, and hand bigger refactors to the OpenCode harness.
- Business workspace vs Code workspace: the Nexus workspace is the business tenant; a Code workspace is the per-user Coder container.
- Feature flag `code` is opt-in: off for every role until the deployment enables it in nexus_config.feature_flags."""

_HANDOFF_PHRASES = (
    "list the repositories",
    "open pull requests",
    "which branches exist",
    "start a coding workspace",
    "how does nexus code work",
    "liste les dépôts",
    "pull requests ouvertes",
    "quelles branches",
    "démarre un espace de code",
    "business workspace vs code workspace",
    "espace de travail business ou espace de code",
    "what is a code workspace",
)


class CodeAgent(IntentAgent):
    """Office agent for Nexus Code (repos, Coder workspaces, reviews).

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi CodeAgent
    """

    name: str = "Code"
    description: str = (
        "Office agent for Nexus Code. Lists repositories, branches, and pull "
        "requests, edits the open repo's sandbox checkout, and explains Coder "
        "workspaces, reviews, and how Code is built, from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = feature_system_prompt(
        name="Code",
        class_name="CodeAgent",
        feature="Code",
        role="You work on the workspace's repositories and explain Nexus Code.",
        context=(
            "On a Code page you receive an open-feature block (feature: code) and, "
            "with a repo open, an Open Code repository block (repo_id, branch). "
            "Repo tools default to that repo; sandbox tools act on its checkout "
            "once the Coder runtime is ready."
        ),
        tasks="""1. "What can I do here?": answer from <capabilities>, tied to real repos (list_code_repositories).
2. "How is it built?": read <code_map> files first, then explain with paths.
3. Repo questions: list_code_branches, list_pull_requests.
4. Edits in the open repo: read_coding_file / write_coding_file / run_in_coding_sandbox; run_coding_harness_task for large multi-file changes. If no sandbox is bound, say so instead of guessing.""",
        capabilities=CODE_CAPABILITIES,
        code_map=CODE_CODE_MAP,
        constraints="- Never push, merge, or delete branches: you have no tools for that.",
    )
    suggestions: list[dict] = [
        {"label": "What can you do?", "value": "What can I do in Code?"},
        {
            "label": "How is it built?",
            "value": "How does Nexus bind a chat to a Coder workspace? Read the code and cite files.",
        },
        {
            "label": "Pull requests",
            "value": "List the open pull requests of this repo.",
        },
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        return feature_handoff_intents("Code", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        from naas_abi.agents.tools.code_tools import code_tools
        from naas_abi.agents.tools.nexus_source_tools import nexus_source_tools

        tools: list = code_tools()
        try:
            from naas_abi.agents.tools.coding_tools import coding_tools

            tools += coding_tools()
        except Exception as exc:  # noqa: BLE001
            logger = __import__("logging").getLogger(__name__)
            logger.debug("coding tools unavailable: %s", exc)
        return tools + nexus_source_tools()

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
    ) -> "CodeAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
