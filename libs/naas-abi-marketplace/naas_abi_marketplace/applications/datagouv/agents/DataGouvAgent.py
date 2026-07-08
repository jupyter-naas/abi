from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class DataGouvAgent(IntentAgent):
    name: str = "DataGouv"
    description: str = "Helps you interact with DataGouv for open data and public datasets."
    system_prompt: str = """<role>
You are a DataGouv Agent with expertise in open data, public datasets, and data discovery.
</role>

<objective>
Help users understand DataGouv capabilities and access open data, datasets, and public information.
</objective>

<context>
You currently do not have access to DataGouv tools. You can only provide general information and guidance about DataGouv services and data access.
</context>

<tasks>
- Provide information about DataGouv features
- Explain open data and dataset discovery
- Guide users on data access and usage
</tasks>

<operating_guidelines>
- Provide clear, accurate information about open data
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or retrieve datasets without tools
- Only provide general information and guidance
- Do not make assumptions about dataset availability or content
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "DataGouvAgent":

        from naas_abi_marketplace.applications.datagouv import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about DataGouv features",
                intent_type=IntentType.RAW,
                intent_target="DataGouv is a platform for open data and public datasets. I can provide general information, but I currently do not have access to DataGouv tools to retrieve datasets."
            ),
            Intent(
                intent_value="Understand open data and dataset discovery",
                intent_type=IntentType.RAW,
                intent_target="Open data involves publicly available datasets that can be freely used. I can explain the concepts, but I currently do not have access to tools to retrieve datasets."
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
