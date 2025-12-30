from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)
from naas_abi_marketplace.applications.google_maps import ABIModule

NAME = "Google Maps"
DESCRIPTION = "Helps you interact with Google Maps for location services and geocoding."
SYSTEM_PROMPT = """<role>
You are a Google Maps Agent with expertise in location services, geocoding, and mapping operations.
</role>

<objective>
Help users understand Google Maps capabilities and access location data, directions, and geocoding services.
</objective>

<context>
You currently do not have access to Google Maps tools. You can only provide general information and guidance about Google Maps services and location operations.
</context>

<tasks>
- Provide information about Google Maps features
- Explain location services and geocoding
- Guide users on mapping best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about location services
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or retrieve location data without tools
- Only provide general information and guidance
- Do not make assumptions about locations or directions
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
            intent_value="Get information about Google Maps features",
            intent_type=IntentType.RAW,
            intent_target="Google Maps provides location services, geocoding, directions, and mapping data. I can provide general information, but I currently do not have access to Google Maps tools to retrieve location data."
        ),
        Intent(
            intent_value="Understand location services and geocoding",
            intent_type=IntentType.RAW,
            intent_target="Location services involve converting addresses to coordinates and finding directions. I can explain the concepts, but I currently do not have access to tools to perform geocoding."
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return GoogleMapsAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class GoogleMapsAgent(IntentAgent):
    pass

