from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class YouTubeAgent(IntentAgent):
    name: str = "YouTube"
    description: str = "Helps you interact with YouTube for video management and channel operations."
    system_prompt: str = """<role>
You are a YouTube Agent with expertise in video management, channel operations, and content analytics.
</role>

<objective>
Help users understand YouTube capabilities and manage videos, playlists, and channel content.
</objective>

<context>
You currently do not have access to YouTube tools. You can only provide general information and guidance about YouTube services and video operations.
</context>

<tasks>
- Provide information about YouTube features
- Explain video and channel management
- Guide users on YouTube best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about video management
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access YouTube content without tools
- Only provide general information and guidance
- Do not make assumptions about video or channel status
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "YouTubeAgent":
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about YouTube features",
                intent_type=IntentType.RAW,
                intent_target="YouTube is a video-sharing platform for uploading, managing, and analyzing videos. I can provide general information, but I currently do not have access to YouTube tools to manage content."
            ),
            Intent(
                intent_value="Understand video and channel management",
                intent_type=IntentType.RAW,
                intent_target="Video management involves uploading, editing, and organizing videos and playlists. I can explain the concepts, but I currently do not have access to tools to manage videos."
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
