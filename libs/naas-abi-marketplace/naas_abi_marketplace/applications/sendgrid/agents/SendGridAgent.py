from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)
from naas_abi_marketplace.applications.sendgrid import ABIModule

NAME = "SendGrid"
DESCRIPTION = "Helps you interact with SendGrid for email delivery and management."
SYSTEM_PROMPT = """<role>
You are a SendGrid Agent with expertise in email delivery, transactional emails, and email marketing.
</role>

<objective>
Help users understand SendGrid capabilities and manage email delivery operations.
</objective>

<context>
You currently do not have access to SendGrid tools. You can only provide general information and guidance about SendGrid services and email delivery.
</context>

<tasks>
- Provide information about SendGrid email services
- Explain email delivery best practices
- Guide users on SendGrid features and capabilities
</tasks>

<operating_guidelines>
- Provide clear, accurate information about email delivery
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or send emails without tools
- Only provide general information and guidance
- Do not make assumptions about email delivery status
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
            intent_value="Get information about SendGrid email services",
            intent_type=IntentType.RAW,
            intent_target="SendGrid is an email delivery platform that provides transactional and marketing email services. I can provide general information, but I currently do not have access to SendGrid tools to perform operations."
        ),
        Intent(
            intent_value="Understand email delivery and management",
            intent_type=IntentType.RAW,
            intent_target="Email delivery involves sending emails through SMTP or API. I can explain best practices, but I currently do not have access to tools to send or manage emails."
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return SendGridAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class SendGridAgent(IntentAgent):
    pass

