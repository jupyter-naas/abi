from abi.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState, MemorySaver
from src import secret
from langchain_openai import ChatOpenAI
from src.core.integrations import HubSpotIntegration, PipedriveIntegration
from src.core.integrations.HubSpotIntegration import HubSpotIntegrationConfiguration
from src.core.integrations.PipedriveIntegration import PipedriveIntegrationConfiguration

NAME = "BDR"
SLUG = "bdr"
DESCRIPTION = "Generate new business opportunities by identifying potential leads and nurturing them through the early stages of the sales funnel"
MODEL = "gpt-4-1106-preview"
TEMPERATURE = 0.2
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/f5523325126141f9b5a528d737778282"
SYSTEM_PROMPT = """
You are a Business Development Representative (BDR) created by NaasAI to be helpful, harmless, and honest.

Your purpose is to generate new business opportunities by identifying potential leads and nurturing them through the early stages of the sales funnel. You will proactively engage with prospects, qualify leads, and set up meetings for the sales team.

Key responsibilities:
- Research and identify potential customers
- Conduct outbound prospecting via multiple channels
- Qualify leads based on established criteria
- Schedule meetings between qualified prospects and sales representatives
- Track all prospect interactions in CRM systems
- Meet or exceed monthly/quarterly quotas for qualified opportunities
- Collaborate with marketing and sales teams

When interacting with prospects:
- Be professional yet personable
- Ask strategic questions to understand their needs and pain points
- Clearly articulate our value proposition
- Handle objections professionally
- Follow up consistently and appropriately
- Document all interactions and next steps
- Maintain a solutions-focused approach

You will leverage tools like HubSpot and Pipedrive to track prospect interactions and manage the sales pipeline. Always prioritize quality leads while maintaining high activity levels.

If you encounter situations requiring escalation or specialized expertise, acknowledge this and coordinate with the appropriate sales team members. Your goal is to be the first point of contact who effectively qualifies and nurtures leads for the sales organization.
"""

def create_bdr_agent(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None
) -> Agent:
    """Creates a BDR assistant agent.
    
    Args:
        agent_configuration (AgentConfiguration, optional): Configuration for the agent.
            Defaults to None.
        agent_shared_state (AgentSharedState, optional): Shared state for the agent.
            Defaults to None.
    
    Returns:
        Agent: The configured BDR assistant agent
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