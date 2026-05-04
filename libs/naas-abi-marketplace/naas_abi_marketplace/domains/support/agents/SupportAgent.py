import json
from pathlib import Path
from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

INTENTS_FILE = Path(__file__).resolve().parent / "intents" / "SupportAgentIntents.json"

# Allowlisted GitHub integration tools for SupportAgent.get_tools (single source of truth).
_SUPPORT_GITHUB_REST_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "github_create_issue_comment",
        "github_get_issue",
        "github_list_issues",
        "github_list_issue_comments",
        "github_list_repository_contributors",
        "github_list_organization_repositories",
    }
)
_SUPPORT_GITHUB_GRAPHQL_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "githubgraphql_list_priorities",
        "githubgraphql_get_project_node_id",
    }
)


class SupportAgent(IntentAgent):
    """Support agent: drafts and creates GitHub issues; lists and inspects repository issues."""

    name: str = "Support"
    description: str = (
        "Handle support requests: capture feedback, draft rich GitHub issues, list and "
        "inspect open issues in the configured repository."
    )
    logo_url: str = "https://t3.ftcdn.net/jpg/05/10/88/82/360_F_510888200_EentlrpDCeyf2L5FZEeSfgYaeiZ80qAU.jpg"
    system_prompt: str = """<role>
You are the Support agent for colleagues using the platform. You turn feedback into actionable GitHub issues and help users see what is already open in the repository.
</role>

<objective>
After the user’s first message describing a new bug, enhancement, or doc gap, respond with a concrete draft issue (title, body, labels) inferred from that message. Refine only if needed; do not block on exhaustive Q&A.
When asked, report on open issues: list them, fetch a specific issue, or read issue comments using the appropriate tools.
</objective>

<context>
You receive messages from end users and support staff.
Default repository for new issues: [GITHUB_REPOSITORY].
GitHub project id (for your awareness, if the user references project scope): [GITHUB_PROJECT_ID].
</context>

<tasks>
Create issue (feature request, bug report, or documentation):
- Classify the request (bug, enhancement, or documentation).
- Infer priority (P1 urgent/high impact, P2 normal, P3 low) from severity, scope, and wording.
- From the first user message, infer area, behaviour, and impact; fill gaps in the draft with short “unknown / not stated” notes or reasonable assumptions rather than long questionnaires.
- Ask at most one or two targeted follow-ups only when something essential is missing (e.g. no repro at all for a bug, or unsafe to guess scope). Never reply with a long bulleted “please provide” checklist.
- Present the draft (title, body, label list) and obtain explicit approval before calling support_bug_report or support_feature_request.
- After creation, confirm issue number and URL. Use github_create_issue_comment only when the user asks to add information to an existing issue.

List and inspect issues:
- Use github_list_issues for open (or filtered) issues in the default or user-named repo.
- Use github_get_issue and github_list_issue_comments for a specific issue when the user needs details or thread context.
- Use github_list_repository_contributors to verify assignee usernames when the user requests assignment. Use github_list_organization_repositories when the user names an org and you need to confirm an allowed repository name.

Project management:
- Use githubgraphql_get_project_node_id to get the project node id.
- Use githubgraphql_list_priorities to list the priorities.
</tasks>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- First reply style: brief acknowledgment, then the full draft in one go (or a very short lead-in plus the draft). No interrogation preambles like “Let’s gather more details” with many bullets.
- Draft for review (plain professional wording, no emoji):
  - Title: imperative or clear outcome, no marketing tone.
  - Body: compact markdown. Use sections only as needed: Summary; Context; Steps / Expected vs Actual (bugs); Proposed behaviour (features); Notes. State unknowns briefly instead of asking the user to list them all up front.
  - Priority: use the id returned by githubgraphql_list_priorities in the workflow tools; keep labels aligned with priority.
- Create the issue using support_feature_request and support_bug_report only after the user approves the draft.
</operating_guidelines>

<constraints>
- Tone: concise, neutral, business appropriate. No emoji or informal filler.
- Do not ask the user to write title/body from scratch; you propose and they confirm or edit.
- Do not dump multi-item “Could you please provide:” lists; prefer one draft plus optional single follow-up.
- Use only the tools listed in this prompt. Pass labels as a list of strings (List[str]), never a serialized string.
- Stay within support and repository issue scope; do not answer unrelated questions.
</constraints>
"""
    suggestions: list[dict[str, str]] = [
        {
            "label": "Feature Request",
            "value": "As a user, I would like to: {{Feature Request}}",
        },
        {
            "label": "Report Bug",
            "value": "Report a bug on: {{Bug Description}}",
        },
    ]
    model = "gpt-4.1-mini"

    @staticmethod
    def get_intents(file_path: Path | str) -> list[Intent]:
        """Load intents from JSON. Intent targets must name real tools."""
        path = Path(file_path)
        with path.open(encoding="utf-8") as file:
            raw_intents: list[dict[str, str]] = json.load(file)

        result: list[Intent] = []
        for row in raw_intents:
            kind = row["intent_type"]
            if kind == "RAW":
                result.append(
                    Intent(
                        intent_type=IntentType.RAW,
                        intent_value=row["intent_value"],
                        intent_target=row["intent_target"],
                    )
                )
            elif kind == "AGENT":
                result.append(
                    Intent(
                        intent_type=IntentType.AGENT,
                        intent_value=row["intent_value"],
                        intent_target=row["intent_target"],
                    )
                )
            elif kind == "TOOL":
                result.append(
                    Intent(
                        intent_type=IntentType.TOOL,
                        intent_value=row["intent_value"],
                        intent_target=row["intent_target"],
                    )
                )
            else:
                raise ValueError(f"Unknown intent_type in {path}: {kind!r}")
        return result

    intents: list[Intent] = get_intents(INTENTS_FILE)

    @staticmethod
    def get_tools(github_access_token: str) -> list:
        from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
            GitHubGraphqlIntegrationConfiguration,
        )
        from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
            as_tools as GitHubGraphqlIntegration_tools,
        )
        from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
            GitHubIntegrationConfiguration,
        )
        from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
            as_tools as GitHubIntegration_tools,
        )
        from naas_abi_marketplace.domains.support.workflows.FeatureRequestWorkflow import (
            FeatureRequestWorkflow,
            FeatureRequestWorkflowConfiguration,
        )
        from naas_abi_marketplace.domains.support.workflows.ReportBugWorkflow import (
            ReportBugWorkflow,
            ReportBugWorkflowConfiguration,
        )

        github_integration_config = GitHubIntegrationConfiguration(
            access_token=github_access_token,
        )
        github_graphql_integration_config = GitHubGraphqlIntegrationConfiguration(
            access_token=github_access_token
        )

        all_github_rest_tools = GitHubIntegration_tools(github_integration_config)
        tools: list = [
            t
            for t in all_github_rest_tools
            if t.name in _SUPPORT_GITHUB_REST_TOOL_NAMES
        ]
        tools += [
            t
            for t in GitHubGraphqlIntegration_tools(github_graphql_integration_config)
            if t.name in _SUPPORT_GITHUB_GRAPHQL_TOOL_NAMES
        ]

        report_bug_workflow = ReportBugWorkflow(
            ReportBugWorkflowConfiguration(
                github_integration_config=github_integration_config,
                github_graphql_integration_config=github_graphql_integration_config,
            )
        )
        tools += report_bug_workflow.as_tools()

        feature_request_workflow = FeatureRequestWorkflow(
            FeatureRequestWorkflowConfiguration(
                github_integration_config=github_integration_config,
                github_graphql_integration_config=github_graphql_integration_config,
            )
        )
        tools += feature_request_workflow.as_tools()
        return tools

    @staticmethod
    def build_system_prompt(
        github_repository: str,
        github_project_id: str | int,
        tools: list,
    ) -> str:
        prompt = SupportAgent.system_prompt.replace(
            "[TOOLS]", "\n".join([f"- {t.name}: {t.description}" for t in tools])
        )
        prompt = prompt.replace("[GITHUB_REPOSITORY]", str(github_repository))
        prompt = prompt.replace("[GITHUB_PROJECT_ID]", str(github_project_id))
        return prompt

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "SupportAgent":
        from naas_abi_marketplace.domains.support import ABIModule

        module = ABIModule.get_instance()
        secret = module.engine.services.secret
        github_project_id = module.configuration.github_project_id
        default_repository = module.configuration.default_repository
        github_access_token = secret.get("GITHUB_ACCESS_TOKEN")

        from langchain_openai import ChatOpenAI
        from pydantic import SecretStr

        model = ChatOpenAI(
            model=cls.model, api_key=SecretStr(secret.get("OPENAI_API_KEY"))
        )
        tools = cls.get_tools(github_access_token)
        system_prompt = cls.build_system_prompt(
            default_repository, github_project_id, tools
        )

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=system_prompt)

        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=model,
            tools=tools,
            agents=[],
            intents=cls.intents,
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
