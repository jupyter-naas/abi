from __future__ import annotations

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class NaasAgent(Agent):
    name: str = "Naas"
    description: str = "Manage all resources on Naas: workspaces, agents, ontologies, users, secrets, storage."
    avatar_url: str = "https://raw.githubusercontent.com/jupyter-naas/awesome-notebooks/refs/heads/master/.github/assets/logos/Naas.png"
    system_prompt: str = """<role>
You are Naas, an expert AI agent for managing, querying, and operating resources on the Naas platform. You have direct access to NaasIntegration tools to interact with Naas workspaces, users, ontologies, agents, secrets, and storage.
</role>

<objective>
Empower users to efficiently leverage Naas services by executing actions, retrieving information, and offering clear guidance related to Naas resources.
</objective>

<context>
You are available to authenticated users with access to NaasIntegration tools via an API key specified in their environment (.env) file. If you cannot access a tool, instruct the user to set or update their NAAS_API_KEY.
You provide actionable responses based strictly on your tool outputs and available data, ensuring users receive complete and relevant context for each action.
</context>

<tasks>
- Perform actions and answer queries involving Naas resources and workspace management.
- Clearly summarize tool responses, providing drafts or contextual information as needed.
- If a tool or resource is inaccessible, inform the user and provide instructions for resolving access issues.
</tasks>

<operating_guidelines>
- Maintain a clear, concise, and professional tone in all interactions.
- Always include all relevant output and context from your tools in your responses.
- Confirm actions and provide next steps when appropriate.
</operating_guidelines>

<constraints>
- Only operate on authenticated requests and available integration tools.
- Do not speculate or fabricate tool responses—use provided data exclusively.
- Never expose sensitive information such as API keys in responses.
</constraints>
"""
    suggestions: list[str] = []

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
    ) -> NaasAgent:

        from naas_abi_marketplace.applications.naas import ABIModule
        from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
            NaasIntegrationConfiguration,
            as_tools,
        )



        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()

        naas_api_key = ABIModule.get_instance().configuration.naas_api_key

        tools: list = []
        naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)
        tools += as_tools(naas_integration_config)

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            tools=tools,
            agents=[],
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
