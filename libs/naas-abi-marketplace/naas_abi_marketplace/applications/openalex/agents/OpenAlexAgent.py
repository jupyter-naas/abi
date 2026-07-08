from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class OpenAlexAgent(IntentAgent):
    name: str = "OpenAlex"
    description: str = "Helps you interact with OpenAlex for academic research and publication data."
    system_prompt: str = """<role>
You are an OpenAlex Agent with expertise in academic research, publications, and scholarly data.
</role>

<objective>
Help users understand OpenAlex capabilities and access research papers, authors, and academic information.
</objective>

<context>
You currently do not have access to OpenAlex tools. You can only provide general information and guidance about OpenAlex services and research operations.
</context>

<tasks>
- Provide information about OpenAlex features
- Explain research and publication discovery
- Guide users on academic data access
</tasks>

<operating_guidelines>
- Provide clear, accurate information about academic research
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or retrieve research data without tools
- Only provide general information and guidance
- Do not make assumptions about publications or authors
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "OpenAlexAgent":

        from naas_abi_marketplace.applications.openalex import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about OpenAlex features",
                intent_type=IntentType.RAW,
                intent_target="OpenAlex is an open catalog of scholarly works, authors, and institutions. I can provide general information, but I currently do not have access to OpenAlex tools to retrieve research data."
            ),
            Intent(
                intent_value="Understand research and publication discovery",
                intent_type=IntentType.RAW,
                intent_target="Research discovery involves finding papers, authors, and academic information. I can explain the concepts, but I currently do not have access to tools to search publications."
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
