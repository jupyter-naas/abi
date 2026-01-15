from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)

NAME = "PostgreSQL"
DESCRIPTION = "A PostgreSQL Assistant for managing database operations."
MODEL = "gpt-4"
TEMPERATURE = 0
AVATAR_URL = "https://logo.clearbit.com/postgresql.org"
SYSTEM_PROMPT = """
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

SUGGESTIONS: list[str] = []


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> Optional[IntentAgent]:
    # Set model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import model

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Set shared state
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    tools: list = []

    # Add integration based on available credentials
    from naas_abi_marketplace.applications.postgres import ABIModule
    from naas_abi_marketplace.applications.postgres.integrations.PostgresIntegration import (
        PostgresIntegrationConfiguration,
        as_tools,
    )

    integration_config = PostgresIntegrationConfiguration(
        host=ABIModule.get_instance().configuration.postgres_host,
        port=int(ABIModule.get_instance().configuration.postgres_port),
        database=ABIModule.get_instance().configuration.postgres_dbname,
        user=ABIModule.get_instance().configuration.postgres_user,
        password=ABIModule.get_instance().configuration.postgres_password,
    )
    tools += as_tools(integration_config)

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

    return PostgresAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=[],
        intents=intents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )


class PostgresAgent(IntentAgent):
    pass
