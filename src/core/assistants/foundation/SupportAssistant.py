from langchain_openai import ChatOpenAI
from fastapi import APIRouter
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.core.integrations.GithubGraphqlIntegration import GithubGraphqlIntegrationConfiguration
from src.core.integrations.GithubIntegration import GithubIntegrationConfiguration
from src.core.workflows.support.GitHubSupportWorkflows import GitHubSupportWorkflows, GitHubSupportWorkflowsConfiguration
from src.core.assistants.prompts.support_prompt import SUPPORT_CHAIN_OF_THOUGHT_PROMPT

AVATAR_URL = "https://t3.ftcdn.net/jpg/05/10/88/82/360_F_510888200_EentlrpDCeyf2L5FZEeSfgYaeiZ80qAU.jpg"
DESCRIPTION = "A Support Assistant that helps to get any feedbacks/bugs or needs from user."
SUPPORT_agent_INSTRUCTIONS = f"""
You are a support assistant focusing on answering user requests and creating features requests or reporting bugs.

Be sure to follow the chain of thought: {SUPPORT_CHAIN_OF_THOUGHT_PROMPT}

You MUST be sure to validate all input arguments before executing any tool.
Be clear and concise in your responses.
"""
SUGGESTIONS = [
    {
        "label": "Feature Request",
        "value": "As a user, I would like to: [Feature Request]"
    },
    {
        "label": "Report Bug",
        "value": "Report a bug on: [Bug Description]"
    }
]

def create_support_agent(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(
        model="gpt-4o",
        temperature=0, 
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []

    if github_access_token := secret.get('GITHUB_ACCESS_TOKEN'):
        github_integration_config = GithubIntegrationConfiguration(access_token=github_access_token)
        github_graphql_integration_config = GithubGraphqlIntegrationConfiguration(access_token=github_access_token)

        # Add GetIssuesWorkflow tool
        get_issues_workflow = GitHubSupportWorkflows(GitHubSupportWorkflowsConfiguration(
            github_integration_config=github_integration_config,
            github_graphql_integration_config=github_graphql_integration_config,
        ))
        tools += get_issues_workflow.as_tools()
    
    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SUPPORT_agent_INSTRUCTIONS)
    
    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return SupportAssistant(
        name="support_agent", 
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    )

class SupportAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "support", 
        name: str = "Support Assistant", 
        description: str = "API endpoints to call the Support assistant completion.", 
        description_stream: str = "API endpoints to call the Support assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)