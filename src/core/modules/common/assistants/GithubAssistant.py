from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from src.core.apps.terminal_agent.terminal_style import print_tool_usage, print_tool_response
from src.core.modules.common.integrations import GithubIntegration, GithubGraphqlIntegration
from src.core.modules.common.integrations.GithubIntegration import GithubIntegrationConfiguration
from src.core.modules.common.integrations.GithubGraphqlIntegration import GithubGraphqlIntegrationConfiguration
from src.core.modules.support.assistants.SupportAssistant import create_agent as create_support_agent
from src.core.modules.common.prompts.responsabilities_prompt import RESPONSIBILITIES_PROMPT

DESCRIPTION = "A GitHub Assistant with access to GitHub Integration tools."
AVATAR_URL = "https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"
SYSTEM_PROMPT = f"""
You are a GitHub Assistant with access to GitHub Integration tools.
If you don't have access to any tool, ask the user to set their access token in .env file.
Always be clear and professional in your communication while helping users interact with GitHub services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.

{RESPONSIBILITIES_PROMPT}
"""

def create_github_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None
):
    # Init
    tools = []
    agents = []

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            on_tool_usage=lambda message: print_tool_usage(message.tool_calls[0]['name']),
            on_tool_response=lambda message: print_tool_response(f'\n{message.content}'),
            system_prompt=SYSTEM_PROMPT
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)
        
    # Set model
    model = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )
    
    # Add tools
    if secret.get('GITHUB_ACCESS_TOKEN'):    
        github_integration_config = GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN'))
        tools += GithubIntegration.as_tools(github_integration_config)

        github_graphql_integration_config = GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN'))
        tools += GithubGraphqlIntegration.as_tools(github_graphql_integration_config)

    # Add agents
    agents.append(create_support_agent(AgentSharedState(thread_id=1), agent_configuration))
        
    return GithubAssistant(
        name="github_agent",
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class GithubAssistant(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "github", 
        name: str = "Github Assistant", 
        description: str = "API endpoints to call the Github assistant completion.", 
        description_stream: str = "API endpoints to call the Github assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)