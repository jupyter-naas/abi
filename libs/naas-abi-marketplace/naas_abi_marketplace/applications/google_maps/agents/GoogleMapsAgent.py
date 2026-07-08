from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class GoogleMapsAgent(IntentAgent):
    name: str = "Google Maps"
    description: str = "Helps you interact with Google Maps for location services and geocoding."
    system_prompt: str = """<role>
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
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "GoogleMapsAgent":

        from naas_abi_marketplace.applications.google_maps import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about Google Maps features",
                intent_type=IntentType.RAW,
                intent_target="Google Maps provides location services, geocoding, directions, and mapping data. I can provide general information, but I currently do not have access to Google Maps tools to retrieve location data.",
            ),
            Intent(
                intent_value="Understand location services and geocoding",
                intent_type=IntentType.RAW,
                intent_target="Location services involve converting addresses to coordinates and finding directions. I can explain the concepts, but I currently do not have access to tools to perform geocoding.",
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
