from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class WhatsAppBusinessAgent(IntentAgent):
    name: str = "WhatsApp_Business"
    description: str = "Helps you interact with WhatsApp Business for business messaging and customer communication."
    system_prompt: str = """<role>
You are a WhatsApp Business Agent with expertise in business messaging, customer communication, and conversation management.
</role>

<objective>
Help users understand WhatsApp Business capabilities and manage business messages, conversations, and customer interactions.
</objective>

<context>
You currently do not have access to WhatsApp Business tools. You can only provide general information and guidance about WhatsApp Business services and messaging operations.
</context>

<tasks>
- Provide information about WhatsApp Business features
- Explain business messaging and customer communication
- Guide users on messaging best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about business messaging
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or send messages without tools
- Only provide general information and guidance
- Do not make assumptions about message delivery or conversation status
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "WhatsAppBusinessAgent":

        from naas_abi_marketplace.applications.whatsapp_business import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about WhatsApp Business features",
                intent_type=IntentType.RAW,
                intent_target="WhatsApp Business provides messaging services for businesses to communicate with customers. I can provide general information, but I currently do not have access to WhatsApp Business tools to send messages."
            ),
            Intent(
                intent_value="Understand business messaging and customer communication",
                intent_type=IntentType.RAW,
                intent_target="Business messaging involves sending messages, managing conversations, and interacting with customers. I can explain the concepts, but I currently do not have access to tools to send messages."
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
