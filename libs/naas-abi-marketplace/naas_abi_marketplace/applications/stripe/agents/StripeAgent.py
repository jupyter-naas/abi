from typing import Optional
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "Stripe"
DESCRIPTION = "Helps you interact with Stripe for payment processing and financial operations."
SYSTEM_PROMPT = """<role>
You are a Stripe Agent with expertise in payment processing, subscriptions, and financial transactions.
</role>

<objective>
Help users understand Stripe capabilities and manage payments, customers, and financial operations.
</objective>

<context>
You currently do not have access to Stripe tools. You can only provide general information and guidance about Stripe services and payment operations.
</context>

<tasks>
- Provide information about Stripe features
- Explain payment processing and subscription management
- Guide users on payment best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about payment processing
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or process payments without tools
- Only provide general information and guidance
- Do not make assumptions about payment status or transactions
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
            intent_value="Get information about Stripe features",
            intent_type=IntentType.RAW,
            intent_target="Stripe is a payment processing platform for accepting payments and managing subscriptions. I can provide general information, but I currently do not have access to Stripe tools to process payments."
        ),
        Intent(
            intent_value="Understand payment processing and subscriptions",
            intent_type=IntentType.RAW,
            intent_target="Payment processing involves accepting payments, managing customers, and handling subscriptions. I can explain the concepts, but I currently do not have access to tools to process payments."
        ),
    ]

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    return StripeAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model.model,
        tools=tools,
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class StripeAgent(IntentAgent):
    pass

