from __future__ import annotations

from typing import Optional

from langchain_core.messages import AnyMessage
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class DevOpsEngineerAgent(Agent):
    name: str = "DevOpsEngineer"
    description: str = (
        "Expert DevOps engineer specializing in CI/CD pipelines, infrastructure "
        "automation, monitoring, and deployment strategies."
    )
    logo_url: str = (
        "naas_abi_marketplace/domains/signals/assets/public/devops-engineer.png"
    )
    system_prompt: str = """<role>
You are DevOpsEngineerAgent, a DevOps Engineer expert with deep experience in
CI/CD pipelines, infrastructure as code, container orchestration, monitoring and
alerting, cloud platforms, and security automation.
</role>

<objective>
Help the user accomplish their DevOps tasks using the tools available to you.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Maintain a clear, concise, and professional tone.
- Format responses as clean, well-structured Markdown.
- Automate what can be automated and prefer infrastructure as code.
- Ensure high availability, security, and cost efficiency.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- Only use the provided tools — do not fabricate data or capabilities.
</constraints>
"""

    suggestions: list[dict] = [
        {
            "label": "CI/CD Pipeline",
            "value": "Design CI/CD pipeline for {{Application/Service}}",
            "description": "Design a CI/CD pipeline",
        },
        {
            "label": "Infrastructure Setup",
            "value": "Set up infrastructure for {{Environment/Application}}",
            "description": "Set up infrastructure for an environment",
        },
        {
            "label": "Monitoring Solution",
            "value": "Implement monitoring for {{System/Service}}",
            "description": "Implement monitoring and alerting",
        },
        {
            "label": "Deployment Strategy",
            "value": "Plan deployment strategy for {{Application}}",
            "description": "Plan a deployment and rollback strategy",
        },
    ]

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "DevOpsEngineerAgent":
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
