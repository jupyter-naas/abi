from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class GoogleAnalyticsAgent(IntentAgent):
    name: str = "Google Analytics"
    description: str = "Helps you interact with Google Analytics for website analytics and data insights."
    system_prompt: str = """<role>
You are a Google Analytics Agent with expertise in web analytics, data analysis, and reporting.
</role>

<objective>
Help users understand Google Analytics capabilities and access website analytics, reports, and insights.
</objective>

<context>
You currently do not have access to Google Analytics tools. You can only provide general information and guidance about Google Analytics services and analytics operations.
</context>

<tasks>
- Provide information about Google Analytics features
- Explain analytics data and reporting
- Guide users on data analysis best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about web analytics
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access analytics data without tools
- Only provide general information and guidance
- Do not make assumptions about website traffic or metrics
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "GoogleAnalyticsAgent":

        from naas_abi_marketplace.applications.google_analytics import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about Google Analytics features",
                intent_type=IntentType.RAW,
                intent_target="Google Analytics provides website analytics and reporting tools for tracking traffic and user behavior. I can provide general information, but I currently do not have access to Google Analytics tools to retrieve data."
            ),
            Intent(
                intent_value="Understand analytics data and reporting",
                intent_type=IntentType.RAW,
                intent_target="Analytics involves tracking website traffic, user behavior, and generating reports. I can explain the concepts, but I currently do not have access to tools to retrieve analytics data."
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
