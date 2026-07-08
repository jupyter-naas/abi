from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class ZohoAgent(IntentAgent):
    name: str = "Zoho"
    description: str = "Helps you interact with Zoho for business applications and CRM operations."
    system_prompt: str = """<role>
You are a Zoho Agent with expertise in business applications, CRM, and productivity tools.
</role>

<objective>
Help users understand Zoho capabilities and manage business applications, CRM, and productivity workflows.
</objective>

<context>
You currently do not have access to Zoho tools. You can only provide general information and guidance about Zoho services and business operations.
</context>

<tasks>
- Provide information about Zoho features
- Explain CRM and business application management
- Guide users on Zoho best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about business applications
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access Zoho data without tools
- Only provide general information and guidance
- Do not make assumptions about business data or configurations
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "ZohoAgent":

        from naas_abi_marketplace.applications.zoho import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about Zoho features",
                intent_type=IntentType.RAW,
                intent_target="Zoho provides business applications including CRM, email, and productivity tools. I can provide general information, but I currently do not have access to Zoho tools to manage applications."
            ),
            Intent(
                intent_value="Understand CRM and business application management",
                intent_type=IntentType.RAW,
                intent_target="Business application management involves managing CRM data, contacts, and workflows. I can explain the concepts, but I currently do not have access to tools to manage applications."
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
