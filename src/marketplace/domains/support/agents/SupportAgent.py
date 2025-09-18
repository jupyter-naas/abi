from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    
)
from typing import Optional
from src import secret
from pydantic import SecretStr
from abi import logger

NAME = "Support"
MODEL = "gpt-4o"
TEMPERATURE = 0
AVATAR_URL = "https://t3.ftcdn.net/jpg/05/10/88/82/360_F_510888200_EentlrpDCeyf2L5FZEeSfgYaeiZ80qAU.jpg"
DESCRIPTION = (
    "A Support Assistant that helps to get any feedbacks/bugs or needs from user."
)
SYSTEM_PROMPT = """
You are a support assistant focusing on answering user requests and creating features requests or reporting bugs.

Be sure to follow the chain of thought:
1.1. Identify if the user intent:
  - Feature request: New integration with external API, new ontology pipeline, or new workflow
  - Bug report: Issue with existing integration, pipeline, or workflow

1.2. Generate a draft proposition with a title and description based on the user request.

1.3. After explicit user approval use appropriate tool to complete your task: "support_agent_create_bug_report" or "support_agent_create_feature_request".

You MUST be sure to validate all input arguments before executing any tool.
Be clear and concise in your responses.
"""
SUGGESTIONS: list = [
    {
        "label": "Feature Request",
        "value": "As a user, I would like to: [Feature Request]",
    },
    {
        "label": "Report Bug",
        "value": "Report a bug on: [Bug Description]",
    },
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Agent:
    # Init
    model = ChatOpenAI(
        model=MODEL, 
        temperature=TEMPERATURE, 
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    tools: list = []
    from src.marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
        GitHubGraphqlIntegrationConfiguration,
    )
    from src.marketplace.applications.github.integrations.GitHubIntegration import (
        GitHubIntegrationConfiguration,
    )
    from src.marketplace.domains.support.workflows.ReportBugWorkflow import (
        ReportBugWorkflow,
        ReportBugWorkflowConfiguration,
    )
    from src.marketplace.domains.support.workflows.FeatureRequestWorkflow import (
        FeatureRequestWorkflow,
        FeatureRequestWorkflowConfiguration,
    )
    if github_access_token := secret.get("GITHUB_ACCESS_TOKEN"):
        github_integration_config = GitHubIntegrationConfiguration(
            access_token=github_access_token
        )
        github_graphql_integration_config = GitHubGraphqlIntegrationConfiguration(
            access_token=github_access_token
        )

        # Add ReportBugWorkflow tool
        report_bug_workflow = ReportBugWorkflow(
            ReportBugWorkflowConfiguration(
                github_integration_config=github_integration_config,
                github_graphql_integration_config=github_graphql_integration_config,
            )
        )
        tools += report_bug_workflow.as_tools()

        # Add FeatureRequestWorkflow tool
        feature_request_workflow = FeatureRequestWorkflow(
            FeatureRequestWorkflowConfiguration(
                github_integration_config=github_integration_config,
                github_graphql_integration_config=github_graphql_integration_config,
            )
        )
        tools += feature_request_workflow.as_tools()
    else:
        logger.warning("No Github access token found, skipping Github integration")
    return SupportAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class SupportAgent(Agent):
    pass