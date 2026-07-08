from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class GmailAgent(IntentAgent):
    name: str = "Gmail"
    description: str = "Helps you interact with Gmail for email management and operations."
    system_prompt: str = """<role>
You are a Gmail Agent with expertise in email management, messaging, and communication workflows.
</role>

<objective>
Help users understand Gmail capabilities and manage emails, labels, and communication.
</objective>

<context>
You currently do not have access to Gmail tools. You can only provide general information and guidance about Gmail services and email operations.
</context>

<tasks>
- Provide information about Gmail features and capabilities
- Explain email management and organization
- Guide users on Gmail best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about email management
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access emails without tools
- Only provide general information and guidance
- Do not make assumptions about email content or status
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "GmailAgent":

        from naas_abi_marketplace.applications.gmail import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about Gmail features",
                intent_type=IntentType.RAW,
                intent_target="Gmail is Google's email service with features like labels, filters, and search. I can provide general information, but I currently do not have access to Gmail tools to access emails."
            ),
            Intent(
                intent_value="Understand email management and organization",
                intent_type=IntentType.RAW,
                intent_target="Email management involves organizing, searching, and managing emails. I can explain best practices, but I currently do not have access to tools to manage emails."
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
