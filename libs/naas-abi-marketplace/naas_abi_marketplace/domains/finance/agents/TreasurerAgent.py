from __future__ import annotations

from typing import Optional

from langchain_core.messages import AnyMessage
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class TreasurerAgent(Agent):
    name: str = "Treasurer"
    description: str = (
        "Expert treasurer specializing in cash management, financial risk "
        "assessment, investment strategy, and treasury operations."
    )
    logo_url: str = "naas_abi_marketplace/domains/finance/assets/public/treasurer.png"
    system_prompt: str = """<role>
You are TreasurerAgent, a Treasurer expert with deep experience in cash
management, financial risk assessment, investment strategy, treasury operations,
liquidity management, and financial planning.
</role>

<objective>
Help the user accomplish their treasury tasks using the tools available to you.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Maintain a clear, concise, and professional tone.
- Format responses as clean, well-structured Markdown.
- Provide expert-level guidance grounded in treasury best practices.
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
            "label": "Strategy",
            "value": "Develop {{Strategy Type}} for {{Context}}",
            "description": "Develop a treasury or investment strategy",
        },
        {
            "label": "Analysis",
            "value": "Analyze {{Subject}} for {{Purpose}}",
            "description": "Analyze cash, liquidity, or risk",
        },
        {
            "label": "Optimization",
            "value": "Optimize {{Process/System}} for {{Goal}}",
            "description": "Optimize a treasury process or system",
        },
        {
            "label": "Planning",
            "value": "Plan {{Initiative}} for {{Timeframe}}",
            "description": "Plan a treasury initiative",
        },
    ]

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "TreasurerAgent":
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
