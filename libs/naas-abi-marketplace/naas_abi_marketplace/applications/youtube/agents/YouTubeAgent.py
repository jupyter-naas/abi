from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)
from naas_abi_marketplace.applications.youtube import ABIModule

NAME = "YouTube"
DESCRIPTION = "Helps you interact with YouTube for video management and channel operations."
SYSTEM_PROMPT = """<role>
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
SUGGESTIONS: list = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Init
    module = ABIModule.get_instance()

    # Define model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model

    # Define tools (none initially)
    tools: list = []

    # Define intents
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

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return YouTubeAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class YouTubeAgent(IntentAgent):
    pass

