from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.integrations import GithubIntegration, GithubGraphqlIntegration, AiaIntegration
from src.workflows import AssignIssuesToProjectWorkflow, CreateIssueAndAddToProjectWorkflow, GetTopPrioritiesWorkflow

OPERATIONS_ASSISTANT_INSTRUCTIONS = '''You are an Operations Assistant. 

Your primary responsibility is to enhance operational efficiency by acccessing Task and Project management tools.

Start each conversation by:
1. Introducing yourself
2. Displaying this image showing operational metrics:
   ![Ops](https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ops_trend.png)
3. Providing a brief analysis of the week's meetings and tasks (max 3 bullet points)

Always:
1. Provide structured, markdown-formatted responses
2. Be casual but professional in your communication
'''

def create_operations_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get('OPENAI_API_KEY'))
    tools = []

    # Add integrations based on available credentials
    if (naas_key := secret.get('NAAS_API_KEY')) and (li_at := secret.get('li_at')) and (jsessionid := secret.get('jsessionid')):
        tools += AiaIntegration.as_tools(AiaIntegration.AiaIntegrationConfiguration(api_key=naas_key))
    
    if github_token := secret.get('GITHUB_ACCESS_TOKEN'):
        tools += GithubIntegration.as_tools(GithubIntegration.GithubIntegrationConfiguration(access_token=github_token))
        tools += GithubGraphqlIntegration.as_tools(GithubGraphqlIntegration.GithubGraphqlIntegrationConfiguration(access_token=github_token))

    # Add CreateIssueAndAddToProjectWorkflow tool
    tools.append(CreateIssueAndAddToProjectWorkflow.as_tool())
    
    # Add GetTopPrioritiesWorkflow tool
    tools.append(GetTopPrioritiesWorkflow.as_tool())
    
    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=OPERATIONS_ASSISTANT_INSTRUCTIONS
        )
    
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