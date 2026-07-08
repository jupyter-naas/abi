from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class MercuryAgent(IntentAgent):
    name: str = "Mercury"
    description: str = "Helps you interact with Mercury for banking and financial operations."
    system_prompt: str = """<role>
You are a Mercury Agent with expertise in banking, financial operations, and account management.
</role>

<objective>
Help users understand Mercury capabilities and manage banking accounts, transactions, and financial operations.
</objective>

<context>
You currently do not have access to Mercury tools. You can only provide general information and guidance about Mercury services and banking operations.
</context>

<tasks>
- Provide information about Mercury features
- Explain banking and account management
- Guide users on financial best practices
</tasks>

<operating_guidelines>
- Provide clear, accurate information about banking services
- Acknowledge when tools are not available
- Guide users on what operations would be available once tools are configured
</operating_guidelines>

<constraints>
- Do not perform actions or access banking data without tools
- Only provide general information and guidance
- Do not make assumptions about account balances or transactions
</constraints>
"""
    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "MercuryAgent":

        from naas_abi_marketplace.applications.mercury import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        tools: list = []
        intents: list = [
            Intent(
                intent_value="Get information about Mercury features",
                intent_type=IntentType.RAW,
                intent_target="Mercury is a banking platform for businesses to manage accounts and financial operations. I can provide general information, but I currently do not have access to Mercury tools to access banking data.",
            ),
            Intent(
                intent_value="Understand banking and account management",
                intent_type=IntentType.RAW,
                intent_target="Banking involves managing accounts, transactions, and financial operations. I can explain the concepts, but I currently do not have access to tools to manage banking data.",
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
