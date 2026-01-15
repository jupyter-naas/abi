from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Instagram"
DESCRIPTION = "Helps you interact with Instagram for social media management and content operations."
SYSTEM_PROMPT = """<role>
You are an Instagram Agent with expertise in social media management, content creation, and engagement.
</role>

<objective>
Help users understand Instagram capabilities and manage posts, stories, and social media content.
</objective>

<context>
You currently do not have access to Instagram tools. You can only provide general information and guidance about Instagram services and social media operations.
</context>

<tasks>
- Provide information about Instagram features
- Explain content management and engagement strategies
- Guide users on Instagram best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about social media management
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access Instagram content without tools
- Only provide general information and guidance
- Do not make assumptions about account status or content
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
            intent_value="Get information about Instagram features",
            intent_type=IntentType.RAW,
            intent_target="Instagram is a social media platform for sharing photos and videos. I can provide general information, but I currently do not have access to Instagram tools to manage content."
        ),
        Intent(
            intent_value="Understand content management and engagement",
            intent_type=IntentType.RAW,
            intent_target="Content management involves creating, scheduling, and analyzing posts and stories. I can explain the concepts, but I currently do not have access to tools to manage content."
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return InstagramAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class InstagramAgent(IntentAgent):
    pass

