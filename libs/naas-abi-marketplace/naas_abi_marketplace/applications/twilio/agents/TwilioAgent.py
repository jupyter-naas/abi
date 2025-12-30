from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Twilio"
DESCRIPTION = "Helps you interact with Twilio for communication services and messaging."
SYSTEM_PROMPT = """<role>
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

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return TwilioAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class TwilioAgent(IntentAgent):
    pass

