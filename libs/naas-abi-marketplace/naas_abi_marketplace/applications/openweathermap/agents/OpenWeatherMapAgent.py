from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "OpenWeatherMap"
DESCRIPTION = "Helps you interact with OpenWeatherMap for weather data and forecasts."
SYSTEM_PROMPT = """<role>
You are an OpenWeatherMap Agent with expertise in weather data, forecasts, and meteorological information.
</role>

<objective>
Help users understand OpenWeatherMap capabilities and access weather data, forecasts, and climate information.
</objective>

<context>
You currently do not have access to OpenWeatherMap tools. You can only provide general information and guidance about OpenWeatherMap services and weather data.
</context>

<tasks>
- Provide information about OpenWeatherMap features
- Explain weather data and forecast retrieval
- Guide users on meteorological data usage
</tasks>

<operating_guidelines>
- Provide clear, accurate information about weather services
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or retrieve weather data without tools
- Only provide general information and guidance
- Do not make assumptions about current weather conditions
</constraints>
"""
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

    # Define tools (none initially)
    tools: list = []

    # Define intents
    intents: list = [
        Intent(
            intent_value="Get information about OpenWeatherMap features",
            intent_type=IntentType.RAW,
            intent_target="OpenWeatherMap provides weather data, forecasts, and meteorological information. I can provide general information, but I currently do not have access to OpenWeatherMap tools to retrieve weather data.",
        ),
        Intent(
            intent_value="Understand weather data and forecasts",
            intent_type=IntentType.RAW,
            intent_target="Weather data includes current conditions, forecasts, and historical data. I can explain the concepts, but I currently do not have access to tools to retrieve weather data.",
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return OpenWeatherMapAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class OpenWeatherMapAgent(IntentAgent):
    pass
