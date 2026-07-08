from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class NewsAPIAgent(IntentAgent):
    name: str = "NewsAPI"
    description: str = "Helps you interact with NewsAPI for news articles and headlines."
    system_prompt: str = """<role>
You are a NewsAPI Agent with expertise in news aggregation, article retrieval, and media monitoring.
</role>

<objective>
Help users understand NewsAPI capabilities and access news articles, headlines, and media content.
</objective>

<context>
You currently do not have access to NewsAPI tools. You can only provide general information and guidance about NewsAPI services and news retrieval.
</context>

<tasks>
- Provide information about NewsAPI features
- Explain news search and article retrieval
- Guide users on media monitoring best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about news aggregation
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or retrieve articles without tools
- Only provide general information and guidance
- Do not make assumptions about news content or sources
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "NewsAPIAgent":

        from naas_abi_marketplace.applications.newsapi import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about NewsAPI features",
                intent_type=IntentType.RAW,
                intent_target="NewsAPI provides access to news articles and headlines from various sources. I can provide general information, but I currently do not have access to NewsAPI tools to retrieve articles."
            ),
            Intent(
                intent_value="Understand news search and article retrieval",
                intent_type=IntentType.RAW,
                intent_target="News search involves finding articles by keywords, sources, or topics. I can explain the concepts, but I currently do not have access to tools to retrieve articles."
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
