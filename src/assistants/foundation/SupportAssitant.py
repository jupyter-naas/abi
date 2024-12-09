from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.integrations import GithubIntegration, GithubGraphqlIntegration
from src.workflows import CreateIssueAndAddToProjectWorkflow
from src.assistants.prompt import SUPER_ASSISTANT_INSTRUCTIONS

SUPPORT_ASSISTANT_INSTRUCTIONS = SUPER_ASSISTANT_INSTRUCTIONS.format(
    name="Support Assistant",
    role="Technical Support Specialist",
    description="A specialized technical support assistant focused on helping users resolve issues, create GitHub tickets/issues (with Github Integration), and provide comprehensive technical solutions. Combines deep understanding of support processes with technical expertise to deliver efficient and effective assistance."
)

def create_support_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    
    tools = []
    
    # Add integrations based on available credentials
    if github_token := secret.get('GITHUB_ACCESS_TOKEN'):
        tools += GithubIntegration.as_tools(GithubIntegration.GithubIntegrationConfiguration(access_token=github_token))
        tools += GithubGraphqlIntegration.as_tools(GithubGraphqlIntegration.GithubGraphqlIntegrationConfiguration(access_token=github_token))

    # Add CreateIssueAndAddToProjectWorkflow tool
    tools.append(CreateIssueAndAddToProjectWorkflow.as_tool())
    
    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SUPPORT_ASSISTANT_INSTRUCTIONS)
    
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