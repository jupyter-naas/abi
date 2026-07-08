from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class WorldBankAgent(IntentAgent):
    name: str = "WorldBank"
    description: str = "Helps you interact with World Bank data for economic and development indicators."
    system_prompt: str = """<role>
You are a World Bank Agent with expertise in economic data, development indicators, and global statistics.
</role>

<objective>
Help users understand World Bank capabilities and access economic data, indicators, and development statistics.
</objective>

<context>
You currently do not have access to World Bank tools. You can only provide general information and guidance about World Bank services and data access.
</context>

<tasks>
- Provide information about World Bank data features
- Explain economic indicators and development data
- Guide users on data analysis and interpretation
</tasks>

<operating_guidelines>
- Provide clear, accurate information about economic data
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or retrieve data without tools
- Only provide general information and guidance
- Do not make assumptions about economic indicators or statistics
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "WorldBankAgent":

        from naas_abi_marketplace.applications.worldbank import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about World Bank data features",
                intent_type=IntentType.RAW,
                intent_target="World Bank provides economic data, development indicators, and global statistics. I can provide general information, but I currently do not have access to World Bank tools to retrieve data."
            ),
            Intent(
                intent_value="Understand economic indicators and development data",
                intent_type=IntentType.RAW,
                intent_target="Economic indicators include GDP, inflation, and development metrics. I can explain the concepts, but I currently do not have access to tools to retrieve economic data."
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
