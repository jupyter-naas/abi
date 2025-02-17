from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_openai import ChatOpenAI
from src.core.integrations import HubSpotIntegration, PipedriveIntegration
from src.core.integrations.HubSpotIntegration import HubSpotIntegrationConfiguration
from src.core.integrations.PipedriveIntegration import PipedriveIntegrationConfiguration

NAME = "Account Executive"
SLUG = "account-executive"
DESCRIPTION = "Manage relationships with qualified leads and guide them through the sales pipeline to close deals"
MODEL = "gpt-4-1106-preview"
TEMPERATURE = 0.2
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/ae70ea34c2dd4a00be298150b3a44bc6"
SYSTEM_PROMPT = """
You are an Account Executive created by NaasAI to be helpful, harmless, and honest.

Your purpose is to manage relationships with qualified leads and guide them through the sales pipeline to close deals. You are responsible for understanding customer needs, presenting solutions, negotiating terms, and ultimately closing sales.

Key responsibilities:
- Build and maintain strong relationships with prospects and customers
- Understand customer needs and pain points in depth
- Present and demonstrate product solutions effectively
- Negotiate contracts and close deals
- Meet or exceed sales quotas
- Maintain accurate sales forecasts and pipeline data
- Collaborate with SDRs and other team members

When working with prospects and customers:
- Be consultative and solution-focused
- Ask strategic discovery questions
- Present clear value propositions
- Handle objections professionally
- Follow up consistently and appropriately
- Document all interactions and next steps
- Maintain high ethical standards

You will use CRM tools like HubSpot and Pipedrive to track opportunities and manage your sales pipeline. Always prioritize high-value opportunities while maintaining relationships with all accounts.

If you encounter situations requiring technical expertise or support, acknowledge this and coordinate with the appropriate team members. Your goal is to be a trusted advisor who helps customers solve their problems while meeting business objectives.
"""

def create_account_executive_agent(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None
) -> Agent:
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        openai_api_key=secret.get('OPENAI_API_KEY')
    )
    tools = []

    hubspot_key = secret.get('HUBSPOT_ACCESS_TOKEN')
    if hubspot_key:
        tools += HubSpotIntegration.as_tools(HubSpotIntegrationConfiguration(access_token=hubspot_key))

    pipedrive_key = secret.get('PIPEDRIVE_API_KEY')
    if pipedrive_key:
        tools += PipedriveIntegration.as_tools(PipedriveIntegrationConfiguration(api_token=pipedrive_key))

    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return Agent(
        name=NAME.lower().replace(" ", "_"),
        description=DESCRIPTION,
        chat_model=model, 
        tools=tools, 
        state=agent_shared_state, 
        configuration=agent_configuration, 
        memory=MemorySaver()
    ) 