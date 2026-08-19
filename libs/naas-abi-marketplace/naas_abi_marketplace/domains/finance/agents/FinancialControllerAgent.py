from __future__ import annotations

from typing import Optional

from langchain_core.messages import AnyMessage
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class FinancialControllerAgent(Agent):
    name: str = "FinancialController"
    description: str = (
        "Expert financial controller specializing in financial planning, budgeting, "
        "cost analysis, financial controls, and reporting."
    )
    logo_url: str = "naas_abi_marketplace/domains/finance/assets/public/financial-controller.png"
    system_prompt: str = """<role>
You are FinancialControllerAgent, a Financial Controller expert with deep
experience in financial planning, budgeting, cost analysis, financial controls,
financial reporting, and variance analysis.
</role>

<objective>
Help the user accomplish their financial controlling tasks using the tools available to you.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Maintain a clear, concise, and professional tone.
- Format responses as clean, well-structured Markdown.
- Provide expert-level guidance grounded in controlling best practices.
- Consider practical constraints and focus on measurable outcomes.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- Only use the provided tools — do not fabricate data or capabilities.
</constraints>
"""

    suggestions: list[dict] = [
        {
            "label": "Budget Planning",
            "value": "Create budget plan for {{Department/Project}}",
            "description": "Create a budget plan for a department or project",
        },
        {
            "label": "Cost Analysis",
            "value": "Analyze costs for {{Process/Department}}",
            "description": "Analyze costs for a process or department",
        },
        {
            "label": "Financial Controls",
            "value": "Design financial controls for {{Area/Process}}",
            "description": "Design financial controls for an area or process",
        },
        {
            "label": "Variance Analysis",
            "value": "Analyze budget variance for {{Period/Department}}",
            "description": "Analyze budget variance for a period or department",
        },
    ]

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "FinancialControllerAgent":
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
