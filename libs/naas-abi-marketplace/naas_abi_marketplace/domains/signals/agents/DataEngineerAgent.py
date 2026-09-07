from __future__ import annotations

from typing import Optional

from langchain_core.messages import AnyMessage
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class DataEngineerAgent(Agent):
    name: str = "DataEngineer"
    description: str = (
        "Expert data engineer specializing in data pipeline design, ETL processes, "
        "data architecture, and performance optimization."
    )
    logo_url: str = (
        "naas_abi_marketplace/domains/signals/assets/public/data-engineer.png"
    )
    system_prompt: str = """<role>
You are DataEngineerAgent, a Data Engineer expert with deep experience in data
pipelines, ETL/ELT processes, data architecture (warehouses, lakes, lakehouse),
big data technologies, cloud data services, and databases.
</role>

<objective>
Help the user accomplish their data engineering tasks using the tools available to you.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Maintain a clear, concise, and professional tone.
- Format responses as clean, well-structured Markdown.
- Design for scalability, reliability, and maintainability.
- Implement data quality checks and optimize for performance and cost.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- Only use the provided tools — do not fabricate data or capabilities.
</constraints>
"""

    suggestions: list[dict] = [
        {
            "label": "Pipeline Design",
            "value": "Design data pipeline for {{Data Source}} to {{Destination}}",
            "description": "Design a data pipeline",
        },
        {
            "label": "Performance Issue",
            "value": "Troubleshoot performance issue in {{Pipeline/Query}}",
            "description": "Troubleshoot a pipeline or query performance issue",
        },
        {
            "label": "Architecture Review",
            "value": "Review data architecture for {{System/Project}}",
            "description": "Review a data architecture",
        },
        {
            "label": "Data Quality",
            "value": "Implement data quality checks for {{Dataset}}",
            "description": "Implement data quality checks",
        },
    ]

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "DataEngineerAgent":
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
