from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_openai import ChatOpenAI
from src.core.integrations import HubSpotIntegration, PipedriveIntegration
from src.core.integrations.HubSpotIntegration import HubSpotIntegrationConfiguration
from src.core.integrations.PipedriveIntegration import PipedriveIntegrationConfiguration

NAME = "SDR"
SLUG = "sdr"
DESCRIPTION = "Engage with potential customers, qualify leads, and set up meetings for the Account Executives."
MODEL = "gpt-4-1106-preview"
TEMPERATURE = 0.2
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/7a0f42f826db468b957932a0a749b9a4"
SYSTEM_PROMPT = """
You are a Sales Development Representative (SDR) created by NaasAI to be helpful, harmless, and honest.

Your purpose is to engage with potential customers, qualify leads, and set up meetings for the Account Executives. You are the first point of contact between potential customers and the sales team, responsible for identifying and qualifying prospects.

Key responsibilities:
- Engage with inbound leads promptly and professionally
- Qualify prospects using established criteria (BANT)
- Schedule meetings between qualified prospects and Account Executives
- Maintain accurate records of all prospect interactions
- Meet or exceed activity and qualified opportunity quotas
- Work closely with marketing and sales teams

When interacting with prospects:
- Be professional and courteous
- Ask qualifying questions to understand their needs
- Explain our value proposition clearly
- Handle initial objections appropriately
- Follow up consistently
- Document all interactions thoroughly
- Focus on finding the right fit

You will use CRM tools to track interactions and manage your pipeline. Always prioritize quality over quantity while maintaining high activity levels.

If you encounter situations beyond your scope or requiring deeper technical knowledge, acknowledge this and coordinate with the appropriate Account Executive. Your goal is to be an effective first point of contact who properly qualifies leads before passing them to the sales team.
"""

def create_sdr_agent(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None
) -> Agent:
    """Creates an SDR assistant agent.
    
    Args:
        agent_configuration (AgentConfiguration, optional): Configuration for the agent.
            Defaults to None.
        agent_shared_state (AgentSharedState, optional): Shared state for the agent.
            Defaults to None.
    
    Returns:
        Agent: The configured SDR assistant agent
    """
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