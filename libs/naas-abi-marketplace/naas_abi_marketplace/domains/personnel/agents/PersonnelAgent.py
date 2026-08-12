from __future__ import annotations

from typing import Optional

from langchain_core.messages import AnyMessage
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class PersonnelAgent(Agent):
    name: str = "Personnel"
    description: str = (
        "Expert HR professional specializing in recruitment, employee relations, "
        "policy development, and performance management."
    )
    logo_url: str = "naas_abi_marketplace/domains/personnel/assets/public/human-resources-manager.png"
    system_prompt: str = """<role>
You are PersonnelAgent, a Human Resources expert with deep experience in
recruitment & hiring, employee relations, policy development, performance
management, training & development, and compliance.
</role>

<objective>
Help the user accomplish their human resources tasks using the tools available to you.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Maintain a clear, concise, and professional tone.
- Format responses as clean, well-structured Markdown.
- Provide expert-level strategic guidance grounded in HR best practices.
- Flag compliance and regulatory considerations when they apply.
- Consider practical constraints and focus on measurable outcomes.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- Only use the provided tools — do not fabricate data or capabilities.
- Do not give legal advice; recommend qualified counsel for binding questions.
</constraints>
"""

    suggestions: list[dict] = [
        {
            "label": "Job Description",
            "value": "Create job description for {{Role/Position}}",
            "description": "Draft a structured job description for an open role",
        },
        {
            "label": "Interview Questions",
            "value": "Develop interview questions for {{Role}}",
            "description": "Build a competency-based interview guide",
        },
        {
            "label": "HR Policy",
            "value": "Draft HR policy for {{Policy Area}}",
            "description": "Write an internal policy document",
        },
        {
            "label": "Performance Review",
            "value": "Design performance review process for {{Department/Role}}",
            "description": "Design an evaluation cycle and its criteria",
        },
    ]

    @classmethod
    def get_tools(cls) -> list:
        """Load the personnel SPARQL competency-question tools from the
        templatable SPARQL query module. The tools are loaded by name so adding
        a new query to ``PersonnelSparqlQueries.ttl`` requires registering its
        label here as well."""
        from naas_abi_core.module.Module import BaseModule
        from naas_abi_core.modules.templatablesparqlquery import (
            ABIModule as TemplatableSparqlQueryABIModule,
        )
        from naas_abi_marketplace.domains.personnel import ABIModule

        templatable_sparql_query_module: BaseModule = (
            ABIModule.get_instance().engine.modules[
                "naas_abi_core.modules.templatablesparqlquery"
            ]
        )
        assert isinstance(
            templatable_sparql_query_module, TemplatableSparqlQueryABIModule
        ), "TemplatableSparqlQueryABIModule must be a subclass of BaseModule"

        personnel_sparql_tools = [
            "find_active_employees",
            "find_employee_by_id",
            "find_employees_by_status",
            "find_employees_by_organization",
            "find_open_job_positions",
            "find_positions_by_title",
            "find_headcount_by_job_family",
            "find_birth_registrations",
        ]
        return list(templatable_sparql_query_module.get_tools(personnel_sparql_tools))

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "PersonnelAgent":
        from naas_abi_core.engine.context import get_default_model_registry

        # Use the workspace's default chat model from the model registry.
        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()

        tools: list = cls.get_tools()

        agents: list = []

        # Use provided configuration or build one from the class system prompt.
        if agent_configuration is None:
            tools_section = (
                "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
                or ""
            )
            agent_configuration = AgentConfiguration(
                system_prompt=cls.system_prompt.replace("[TOOLS]", tools_section)
            )

        # Use provided shared state or create new one
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

    # ------------------------------------------------------------------
    # Message hooks
    #
    # Already wired: the runtime calls these on every message, you only have
    # to fill in the body. They are observation points -- whatever you return
    # is ignored, and if you raise, the error is logged and swallowed so the
    # conversation keeps going.
    #
    # They run inline on the streaming thread, so keep them quick. Hand slow
    # work (HTTP calls, big writes) off to a queue or a thread yourself.
    # ------------------------------------------------------------------

    def onHumanMessage(self, message: AnyMessage) -> None:
        """Called every time the user sends a new message to this agent.

        Runs once per turn, before the message reaches the model.

        Args:
            message (AnyMessage): The HumanMessage that was just received.
        """
        # Example -- replace with whatever you need:
        # from naas_abi_core.utils.Logger import logger
        # logger.info(f"[{self.name}] human: {message.content}")

    def onAImessage(self, message: AnyMessage, agent_name: str) -> None:
        """Called every time a new AI message is emitted.

        Fires for messages from this agent *and* from any of its sub-agents --
        use ``agent_name`` to tell them apart. Messages that only carry tool
        calls are not reported here.

        Args:
            message (AnyMessage): The AIMessage that was just emitted.
            agent_name (str): Name of the agent that produced the message.
        """
        # Example -- replace with whatever you need:
        # from naas_abi_core.utils.Logger import logger
        # logger.info(f"[{agent_name}] ai: {message.content}")
