from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "WhatsApp_Business"
DESCRIPTION = "Helps you interact with WhatsApp Business for business messaging and customer communication."
SYSTEM_PROMPT = """<role>
You are a WhatsApp Business Agent with expertise in business messaging, customer communication, and conversation management.
</role>

<objective>
Help users understand WhatsApp Business capabilities and manage business messages, conversations, and customer interactions.
</objective>

<context>
You currently do not have access to WhatsApp Business tools. You can only provide general information and guidance about WhatsApp Business services and messaging operations.
</context>

<tasks>
- Provide information about WhatsApp Business features
- Explain business messaging and customer communication
- Guide users on messaging best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about business messaging
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or send messages without tools
- Only provide general information and guidance
- Do not make assumptions about message delivery or conversation status
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
            intent_value="Get information about WhatsApp Business features",
            intent_type=IntentType.RAW,
            intent_target="WhatsApp Business provides messaging services for businesses to communicate with customers. I can provide general information, but I currently do not have access to WhatsApp Business tools to send messages."
        ),
        Intent(
            intent_value="Understand business messaging and customer communication",
            intent_type=IntentType.RAW,
            intent_target="Business messaging involves sending messages, managing conversations, and interacting with customers. I can explain the concepts, but I currently do not have access to tools to send messages."
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return WhatsAppBusinessAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class WhatsAppBusinessAgent(IntentAgent):
    pass

