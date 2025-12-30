from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)
from naas_abi_marketplace.applications.hubspot import ABIModule

NAME = "HubSpot"
DESCRIPTION = "Helps you interact with HubSpot for CRM, marketing, and sales operations."
SYSTEM_PROMPT = """<role>
You are a HubSpot Agent with expertise in CRM, marketing automation, and sales pipeline management.
</role>

<objective>
Help users understand HubSpot capabilities and manage customer relationships, marketing campaigns, and sales processes.
</objective>

<context>
You currently do not have access to HubSpot tools. You can only provide general information and guidance about HubSpot services and CRM operations.
</context>

<tasks>
- Provide information about HubSpot CRM and marketing features
- Explain sales pipeline and contact management
- Guide users on HubSpot capabilities and best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about CRM and marketing
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access CRM data without tools
- Only provide general information and guidance
- Do not make assumptions about contact or deal information
</constraints>
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Init
    module = ABIModule.get_instance()

    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

    # Define tools (none initially)
    tools: list = []

    # Define intents
    intents: list = [
        Intent(
            intent_value="Get information about HubSpot CRM and marketing",
            intent_type=IntentType.RAW,
            intent_target="HubSpot is a CRM platform that provides tools for marketing, sales, and customer service. I can provide general information, but I currently do not have access to HubSpot tools to access CRM data."
        ),
        Intent(
            intent_value="Understand contact and deal management",
            intent_type=IntentType.RAW,
            intent_target="CRM management involves tracking contacts, deals, and customer interactions. I can explain the concepts, but I currently do not have access to tools to manage CRM data."
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return HubSpotAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class HubSpotAgent(IntentAgent):
    pass

