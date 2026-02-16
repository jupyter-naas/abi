from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Gmail"
DESCRIPTION = "Helps you interact with Gmail for email management and operations."
SYSTEM_PROMPT = """<role>
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
            intent_value="Get information about Gmail features",
            intent_type=IntentType.RAW,
            intent_target="Gmail is Google's email service with features like labels, filters, and search. I can provide general information, but I currently do not have access to Gmail tools to access emails.",
        ),
        Intent(
            intent_value="Understand email management and organization",
            intent_type=IntentType.RAW,
            intent_target="Email management involves organizing, searching, and managing emails. I can explain best practices, but I currently do not have access to tools to manage emails.",
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return GmailAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class GmailAgent(IntentAgent):
    pass
