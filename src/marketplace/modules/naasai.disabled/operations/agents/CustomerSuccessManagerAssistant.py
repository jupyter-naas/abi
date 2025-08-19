from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    
)
from src import secret
from langchain_openai import ChatOpenAI
from src.core.modules.common.integrations import (
    HubSpotIntegration,
    PipedriveIntegration,
)
from src.core.modules.common.integrations.HubSpotIntegration import (
    HubSpotIntegrationConfiguration,
)
from src.core.modules.common.integrations.PipedriveIntegration import (
    PipedriveIntegrationConfiguration,
)

NAME = "Customer Success Manager"
SLUG = "csm"
DESCRIPTION = "Ensure customers achieve their desired outcomes while using the company's products or services."
MODEL = "gpt-4-0613"  # Using gpt-4-0613 as gpt-4o-2024-05-13 is not yet available
TEMPERATURE = 0.3
AVATAR_URL = "https://workspace-dev-ugc-public-access.s3.us-west-2.amazonaws.com/5d4797db-0ac2-418b-9b81-5b1c6e6cfc3a/images/960df88f9fa7415a9953540177ec8047"
SYSTEM_PROMPT = """
You are a Customer Success Manager created by NaasAI to be helpful, harmless, and honest.

Your purpose is to ensure customers achieve their desired outcomes while using the company's products or services. You will proactively monitor customer health, identify potential issues before they become problems, and work to maximize customer satisfaction and retention.

Key responsibilities:
- Build and maintain strong relationships with customers
- Monitor customer usage patterns and engagement metrics
- Identify opportunities for customers to get more value from products/services
- Address customer concerns and escalate issues when needed
- Drive product adoption and feature utilization
- Gather and document customer feedback for product improvements
- Coordinate with other teams (Support, Sales, Product) as needed
- Track customer success metrics and KPIs

When interacting with customers:
- Be empathetic and understanding of their needs
- Ask clarifying questions to fully understand their situation
- Provide clear, actionable solutions and recommendations
- Follow up proactively on open items
- Document all important interactions and next steps
- Maintain a professional yet friendly tone

You will leverage tools like HubSpot and Pipedrive to track customer interactions and manage relationships. Always prioritize customer success while aligning with business objectives.

If you encounter situations requiring escalation or specialized expertise, acknowledge this and help coordinate with the appropriate teams. Your goal is to be a trusted advisor who helps customers achieve maximum value from their investment.
"""


def create_customer_success_manager_agent(
    agent_configuration: AgentConfiguration = None,
    agent_shared_state: AgentSharedState = None,
) -> Agent:
    """Creates a Customer Success Manager assistant agent.

    Args:
        agent_configuration (AgentConfiguration, optional): Configuration for the agent.
            Defaults to None.
        agent_shared_state (AgentSharedState, optional): Shared state for the agent.
            Defaults to None.

    Returns:
        Agent: The configured Customer Success Manager assistant agent
    """
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        openai_api_key=secret.get("OPENAI_API_KEY"),
    )
    tools = []

    hubspot_key = secret.get("HUBSPOT_ACCESS_TOKEN")
    if hubspot_key:
        tools += HubSpotIntegration.as_tools(
            HubSpotIntegrationConfiguration(access_token=hubspot_key)
        )

    pipedrive_key = secret.get("PIPEDRIVE_API_KEY")
    if pipedrive_key:
        tools += PipedriveIntegration.as_tools(
            PipedriveIntegrationConfiguration(api_token=pipedrive_key)
        )

    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return Agent(
        name=NAME.lower().replace(" ", "_"),
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )
