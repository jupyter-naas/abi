from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class StripeAgent(IntentAgent):
    name: str = "Stripe"
    description: str = "Helps you interact with Stripe for payment processing and financial operations."
    system_prompt: str = """<role>
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
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "StripeAgent":
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
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
