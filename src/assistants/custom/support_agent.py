from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret

SUPPORT_AGENT_INSTRUCTIONS = """You are a helpful support assistant. Your primary responsibilities are:
1. Help users with their technical issues
2. Create GitHub issues when necessary
3. Search existing GitHub issues for similar problems
4. Provide relevant documentation and solutions

Always try to:
1. Understand the user's problem completely before taking action
2. Search for existing issues before creating new ones
3. Include relevant technical details when creating issues
4. Provide clear and actionable responses to users
"""

def create_support_agent(agent_shared_state: AgentSharedState = None, 
                        agent_configuration: AgentConfiguration = None):
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    from src.integrations import GithubIntegration, GithubGraphqlIntegration
    from src.workflows import CreateIssueAndAddToProjectWorkflow
    
    tools = []
    
    # Add GitHub tools if credentials are available
    if github_token := secret.get('GITHUB_ACCESS_TOKEN'):
        tools += GithubIntegration.as_tools(
            GithubIntegration.GithubIntegrationConfiguration(access_token=github_token)
        )

    if github_graphql_token := secret.get('GITHUB_GRAPHQL_ACCESS_TOKEN'):
        tools += GithubGraphqlIntegration.as_tools(
            GithubGraphqlIntegration.GithubGraphqlIntegrationConfiguration(access_token=github_graphql_token)
        )
    
    # Add issue creation workflow tools
    tools += CreateIssueAndAddToProjectWorkflow.as_tools()
    
    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SUPPORT_AGENT_INSTRUCTIONS)
    
    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return Agent(
        model, 
        tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 