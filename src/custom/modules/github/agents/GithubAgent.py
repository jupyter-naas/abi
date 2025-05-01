from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from fastapi import APIRouter
from ..integrations import GithubIntegration, GithubGraphqlIntegration
from ..integrations.GithubIntegration import GithubIntegrationConfiguration
from ..integrations.GithubGraphqlIntegration import GithubGraphqlIntegrationConfiguration

NAME = "Github Assistant"
MODEL = "gpt-4o"
TEMPERATURE = 0
DESCRIPTION = "A GitHub Assistant with access to GitHub Integration tools."
AVATAR_URL = "https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"
SYSTEM_PROMPT = f"""
You are a GitHub Assistant with access to GitHub Integration tools.
If you don't have access to any tool, ask the user to set their access token in .env file.
Always be clear and professional in your communication while helping users interact with GitHub services.
Always provide all the context (tool response, draft, etc.) to the user in your final response.
"""
SUGGESTIONS = []

def create_agent(
    agent_shared_state: AgentSharedState = None,
    agent_configuration: AgentConfiguration = None
) -> Agent:
    # Init
    tools = []
    agents = []

    # Set model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=secret.get('OPENAI_API_KEY')
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id=0)
        
    # Add tools
    if secret.get('GITHUB_ACCESS_TOKEN'):    
        github_integration_config = GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN'))
        tools += GithubIntegration.as_tools(github_integration_config)

        github_graphql_integration_config = GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN'))
        tools += GithubGraphqlIntegration.as_tools(github_graphql_integration_config)
        
    return GithubAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools, 
        agents=agents,
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 

class GithubAgent(Agent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "github", 
        name: str = NAME, 
        description: str = DESCRIPTION, 
        description_stream: str = "API endpoints to call the Github assistant stream completion.",
        tags: list[str] = []
    ):
        return super().as_api(router, route_name, name, description, description_stream, tags)