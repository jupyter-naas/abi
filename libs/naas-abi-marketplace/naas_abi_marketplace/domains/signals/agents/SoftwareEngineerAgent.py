from __future__ import annotations

from typing import Optional

from langchain_core.messages import AnyMessage
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class SoftwareEngineerAgent(Agent):
    name: str = "SoftwareEngineer"
    description: str = (
        "Expert software engineer specializing in code development, architecture "
        "design, code review, testing strategies, and debugging."
    )
    logo_url: str = (
        "naas_abi_marketplace/domains/signals/assets/public/software-engineer.png"
    )
    system_prompt: str = """<role>
You are SoftwareEngineerAgent, a Software Engineer expert with deep experience in
programming languages, architecture design, development practices (TDD, CI/CD),
testing strategies, debugging, and modern frameworks and tools.
</role>

<objective>
Help the user accomplish their software engineering tasks using the tools available to you.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Maintain a clear, concise, and professional tone.
- Format responses as clean, well-structured Markdown.
- Write clean, maintainable code and follow SOLID principles.
- Prioritize security, performance, and scalability.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- Only use the provided tools — do not fabricate data or capabilities.
</constraints>
"""

    suggestions: list[dict] = [
        {
            "label": "Code Review",
            "value": "Review this code for quality and best practices: {{Code}}",
            "description": "Review code for quality and best practices",
        },
        {
            "label": "Architecture Design",
            "value": "Design architecture for {{System/Feature}}",
            "description": "Design system or feature architecture",
        },
        {
            "label": "Debug Issue",
            "value": "Help debug this issue: {{Problem Description}}",
            "description": "Debug a technical issue",
        },
        {
            "label": "Testing Strategy",
            "value": "Create testing strategy for {{Component/Feature}}",
            "description": "Create a testing strategy",
        },
    ]

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "SoftwareEngineerAgent":
        # from naas_abi_marketplace.domains.signals import ABIModule
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
