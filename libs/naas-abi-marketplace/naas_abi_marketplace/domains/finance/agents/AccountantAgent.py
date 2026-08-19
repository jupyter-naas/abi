from __future__ import annotations

from typing import Optional

from langchain_core.messages import AnyMessage
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class AccountantAgent(Agent):
    name: str = "Accountant"
    description: str = (
        "Expert accountant specializing in financial accounting, bookkeeping, "
        "tax preparation, audit support, and compliance."
    )
    logo_url: str = "naas_abi_marketplace/domains/finance/assets/public/accountant.png"
    system_prompt: str = """<role>
You are AccountantAgent, an Accountant expert with deep experience in financial
accounting (GAAP/IFRS), bookkeeping, tax preparation, audit support, financial
reporting, and regulatory compliance.
</role>

<objective>
Help the user accomplish their accounting tasks using the tools available to you.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Maintain a clear, concise, and professional tone.
- Format responses as clean, well-structured Markdown.
- Ensure accuracy and precision; follow applicable accounting standards.
- Maintain proper documentation and audit trails in recommendations.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- Only use the provided tools — do not fabricate data or capabilities.
- Do not give tax or legal advice that should come from a qualified professional.
</constraints>
"""

    suggestions: list[dict] = [
        {
            "label": "Financial Analysis",
            "value": "Analyze financial statements for {{Company}}",
            "description": "Analyze financial statements for a company",
        },
        {
            "label": "Tax Preparation",
            "value": "Prepare tax documents for {{Tax Year}}",
            "description": "Prepare tax documents for a tax year",
        },
        {
            "label": "Audit Support",
            "value": "Support audit process for {{Audit Area}}",
            "description": "Support an audit process for an area",
        },
        {
            "label": "Compliance Check",
            "value": "Check compliance for {{Regulation/Standard}}",
            "description": "Check compliance against a regulation or standard",
        },
    ]

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "AccountantAgent":
        # from naas_abi_marketplace.domains.finance import ABIModule
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()

        tools: list = []
        agents: list = []

        if agent_configuration is None:
            tools_section = (
                "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
                or ""
            )
            agent_configuration = AgentConfiguration(
                system_prompt=cls.system_prompt.replace("[TOOLS]", tools_section)
            )

        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            tools=tools,
            agents=agents,
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
        )

    def onHumanMessage(self, message: AnyMessage) -> None:
        """Called every time the user sends a new message to this agent."""

    def onAImessage(self, message: AnyMessage, agent_name: str) -> None:
        """Called every time a new AI message is emitted."""
