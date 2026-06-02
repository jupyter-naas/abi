from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class SpotifyAgent(IntentAgent):
    name: str = "Spotify"
    description: str = "Helps you interact with Spotify for music streaming and playlist management."
    system_prompt: str = """<role>
You are a Spotify Agent with expertise in music streaming, playlist management, and audio content.
</role>

<objective>
Help users understand Spotify capabilities and manage playlists, tracks, and music discovery.
</objective>

<context>
You currently do not have access to Spotify tools. You can only provide general information and guidance about Spotify services and music operations.
</context>

<tasks>
- Provide information about Spotify features
- Explain playlist and track management
- Guide users on music discovery and streaming
</tasks>

<operating_guidelines>
- Provide clear, accurate information about music streaming
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access music data without tools
- Only provide general information and guidance
- Do not make assumptions about playlists or track availability
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "SpotifyAgent":
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about Spotify features",
                intent_type=IntentType.RAW,
                intent_target="Spotify is a music streaming platform with playlists, tracks, and discovery features. I can provide general information, but I currently do not have access to Spotify tools to access music data."
            ),
            Intent(
                intent_value="Understand playlist and track management",
                intent_type=IntentType.RAW,
                intent_target="Playlist management involves creating, organizing, and sharing music playlists. I can explain the concepts, but I currently do not have access to tools to manage playlists."
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
