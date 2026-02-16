from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Slack"
DESCRIPTION = "Helps you interact with Slack for team communication and collaboration."
SYSTEM_PROMPT = """<role>
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
            intent_value="Get information about Slack features",
            intent_type=IntentType.RAW,
            intent_target="Slack is a team communication platform for channels, messages, and collaboration. I can provide general information, but I currently do not have access to Slack tools to manage channels.",
        ),
        Intent(
            intent_value="Understand channel and message management",
            intent_type=IntentType.RAW,
            intent_target="Channel management involves organizing conversations, sending messages, and collaborating with teams. I can explain the concepts, but I currently do not have access to tools to manage channels.",
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return SlackAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class SlackAgent(IntentAgent):
    pass
