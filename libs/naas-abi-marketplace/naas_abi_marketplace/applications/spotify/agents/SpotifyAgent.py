from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Spotify"
DESCRIPTION = "Helps you interact with Spotify for music streaming and playlist management."
SYSTEM_PROMPT = """<role>
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
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

    # Define tools (none initially)
    tools: list = []

    # Define intents
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

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return SpotifyAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class SpotifyAgent(IntentAgent):
    pass

