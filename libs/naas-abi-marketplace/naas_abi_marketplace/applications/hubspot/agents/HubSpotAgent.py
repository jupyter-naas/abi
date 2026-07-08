from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class HubSpotAgent(IntentAgent):
    name: str = "HubSpot"
    description: str = "Helps you interact with HubSpot for CRM, marketing, and sales operations."
    system_prompt: str = """<role>
You are a HubSpot Agent with expertise in CRM, marketing automation, and sales pipeline management.
</role>

<objective>
Help users understand HubSpot capabilities and manage customer relationships, marketing campaigns, and sales processes.
</objective>

<context>
You currently do not have access to HubSpot tools. You can only provide general information and guidance about HubSpot services and CRM operations.
</context>

<tasks>
- Provide information about HubSpot CRM and marketing features
- Explain sales pipeline and contact management
- Guide users on HubSpot capabilities and best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about CRM and marketing
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access CRM data without tools
- Only provide general information and guidance
- Do not make assumptions about contact or deal information
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "HubSpotAgent":

        from naas_abi_marketplace.applications.hubspot import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about HubSpot CRM and marketing",
                intent_type=IntentType.RAW,
                intent_target="HubSpot is a CRM platform that provides tools for marketing, sales, and customer service. I can provide general information, but I currently do not have access to HubSpot tools to access CRM data.",
            ),
            Intent(
                intent_value="Understand contact and deal management",
                intent_type=IntentType.RAW,
                intent_target="CRM management involves tracking contacts, deals, and customer interactions. I can explain the concepts, but I currently do not have access to tools to manage CRM data.",
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
