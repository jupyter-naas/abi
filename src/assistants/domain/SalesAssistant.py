from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from src.integrations import HubSpotIntegration
from src.integrations.HubSpotIntegration import HubSpotIntegrationConfiguration
from src.workflows.sales_assistant.CreateHubSpotContactWorkflow import CreateHubSpotContactWorkflow, CreateHubSpotContactWorkflowConfiguration

DESCRIPTION = "A Sales Assistant that helps manage and qualify contacts for sales representatives."
AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/sales_conversion.png"
SYSTEM_PROMPT = """
You are a Sales Assistant.
Your role is to manage and optimize the list of people who interacted with the content, ensuring to extract only the most qualified contacts to feed the sales representatives.

Start each conversation by:
1. Introducing yourself
2. Providing a brief analysis of 'Abi' new interactions (max 3 bullet points)
3. Displaying this image showing contacts reached over weeks:
   ![Contacts Reached](https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/growth_trend.png)

Always:
1. Provide structured, markdown-formatted responses
2. Be casual but professional in your communication
"""

def create_sales_assistant(
        agent_shared_state: AgentSharedState = None, 
        agent_configuration: AgentConfiguration = None
    ) -> Agent:
    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []
    
    if hubspot_access_token := secret.get('HUBSPOT_ACCESS_TOKEN'):
        hubspot_integration_config = HubSpotIntegrationConfiguration(access_token=hubspot_access_token)
        
        tools += HubSpotIntegration.as_tools(hubspot_integration_config)
        
        create_hubspot_contact_workflow = CreateHubSpotContactWorkflow(CreateHubSpotContactWorkflowConfiguration(
            hubspot_integration_config=hubspot_integration_config
        ))
        tools += create_hubspot_contact_workflow.as_tools()
    
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()
    
    return Agent(
        model, 
        tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 