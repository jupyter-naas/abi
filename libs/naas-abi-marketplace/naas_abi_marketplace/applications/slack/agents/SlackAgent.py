from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class SlackAgent(IntentAgent):
    name: str = "Slack"
    description: str = "Helps you interact with Slack for team communication and collaboration."
    system_prompt: str = """<role>
You are a Slack Agent with expertise in team communication, messaging, and collaboration workflows.
</role>

<objective>
Help users understand Slack capabilities and manage channels, messages, and team collaboration.
</objective>

<context>
You currently do not have access to Slack tools. You can only provide general information and guidance about Slack services and communication operations.
</context>

<tasks>
- Provide information about Slack features
- Explain channel and message management
- Guide users on collaboration best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about team communication
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access Slack channels without tools
- Only provide general information and guidance
- Do not make assumptions about channel content or messages
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "SlackAgent":
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about Slack features",
                intent_type=IntentType.RAW,
                intent_target="Slack is a team communication platform for channels, messages, and collaboration. I can provide general information, but I currently do not have access to Slack tools to manage channels."
            ),
            Intent(
                intent_value="Understand channel and message management",
                intent_type=IntentType.RAW,
                intent_target="Channel management involves organizing conversations, sending messages, and collaborating with teams. I can explain the concepts, but I currently do not have access to tools to manage channels."
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
