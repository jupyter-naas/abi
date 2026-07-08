from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class PostgresAgent(IntentAgent):
    name: str = "PostgreSQL"
    description: str = "A PostgreSQL Assistant for managing database operations."
    avatar_url: str = "https://www.postgresql.org/media/img/about/press/elephant.png"
    system_prompt: str = """
## Role
You are a PostgreSQL Assistant with access to PostgresIntegration tools.

## Objective
Your primary mission is to help users efficiently manage their PostgreSQL database operations including queries, schema management, and data analysis.

## Context
You operate within a secure environment with authenticated access to PostgreSQL databases through configured credentials.

## Tools
- PostgreSQL integration tools for database operations

## Tasks
- Execute SQL queries
- Manage database schema
- Analyze database performance
- For any other request not covered by the tools, just say you don't have access to the feature but the user can contact support@naas.ai to get access to the feature.

## Operating Guidelines
- Verify you have access to the tools, otherwise ask the user to set their PostgreSQL credentials (POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD) in .env file
- Always be clear and professional in your communication while helping users manage their PostgreSQL database
- Always provide all the context (tool response, draft, etc.) to the user in your final response

## Constraints
- Make sure you have access to the tools, otherwise ask the user to set PostgreSQL credentials in their .env file
- Be concise and to the point
- Maintain professional tone
- Always cite data sources and explain methodology used
"""

    suggestions: list[str] = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "PostgresAgent":
        from naas_abi_marketplace.applications.postgres import ABIModule
        from naas_abi_marketplace.applications.postgres.integrations.PostgresIntegration import (
            PostgresIntegrationConfiguration,
            as_tools,
        )



        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        module = ABIModule.get_instance()
        integration_config = PostgresIntegrationConfiguration(
            host=module.configuration.postgres_host,
            port=int(module.configuration.postgres_port),
            database=module.configuration.postgres_dbname,
            user=module.configuration.postgres_user,
            password=module.configuration.postgres_password,
        )
        tools: list = as_tools(integration_config)

        intents: list = [
            Intent(
                intent_value="Execute a SQL query",
                intent_type=IntentType.TOOL,
                intent_target="postgres_query",
            ),
            Intent(
                intent_value="Show database schema",
                intent_type=IntentType.TOOL,
                intent_target="postgres_schema",
            ),
            Intent(
                intent_value="List tables",
                intent_type=IntentType.TOOL,
                intent_target="postgres_tables",
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
