from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class OpenWeatherMapAgent(IntentAgent):
    name: str = "OpenWeatherMap"
    description: str = "Helps you interact with OpenWeatherMap for weather data and forecasts."
    system_prompt: str = """<role>
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
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "OpenWeatherMapAgent":
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about OpenWeatherMap features",
                intent_type=IntentType.RAW,
                intent_target="OpenWeatherMap provides weather data, forecasts, and meteorological information. I can provide general information, but I currently do not have access to OpenWeatherMap tools to retrieve weather data."
            ),
            Intent(
                intent_value="Understand weather data and forecasts",
                intent_type=IntentType.RAW,
                intent_target="Weather data includes current conditions, forecasts, and historical data. I can explain the concepts, but I currently do not have access to tools to retrieve weather data."
            ),
        ]

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            embedding_model=embedding_model,
            tools=tools,
            agents=[],
            intents=intents,
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
