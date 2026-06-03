from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class TwilioAgent(IntentAgent):
    name: str = "Twilio"
    description: str = "Helps you interact with Twilio for communication services and messaging."
    system_prompt: str = """<role>
You are a Twilio Agent with expertise in communication services, SMS, voice, and messaging operations.
</role>

<objective>
Help users understand Twilio capabilities and manage messaging, voice calls, and communication services.
</objective>

<context>
You currently do not have access to Twilio tools. You can only provide general information and guidance about Twilio services and communication operations.
</context>

<tasks>
- Provide information about Twilio features
- Explain messaging and voice communication
- Guide users on communication best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about communication services
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or send messages without tools
- Only provide general information and guidance
- Do not make assumptions about message delivery or call status
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "TwilioAgent":
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about Twilio features",
                intent_type=IntentType.RAW,
                intent_target="Twilio provides communication services for SMS, voice calls, and messaging. I can provide general information, but I currently do not have access to Twilio tools to send messages."
            ),
            Intent(
                intent_value="Understand messaging and voice communication",
                intent_type=IntentType.RAW,
                intent_target="Communication services involve sending SMS, making voice calls, and managing messaging workflows. I can explain the concepts, but I currently do not have access to tools to send messages."
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
