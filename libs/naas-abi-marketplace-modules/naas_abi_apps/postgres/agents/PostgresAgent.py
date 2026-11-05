"""PostgreSQL agent: an SDK IntentAgent hosted by the remote ``postgres`` module."""

from __future__ import annotations

from typing import Any

from naas_abi_apps.common.agents import build_agent
from naas_abi_apps.postgres.integrations.PostgresIntegration import (
    PostgresIntegrationConfiguration,
    as_tools,
)
from naas_abi_sdk.agents import Agent, Intent, IntentType

NAME = "PostgreSQL"
DESCRIPTION = "A PostgreSQL Assistant for managing database operations."
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

INTENTS: list[Intent] = [
    Intent(
        intent_value="Execute a SQL query",
        intent_type=IntentType.TOOL,
        intent_target="postgres_execute_query",
    ),
    Intent(
        intent_value="Show database schema",
        intent_type=IntentType.TOOL,
        intent_target="postgres_get_table_schema",
    ),
    Intent(
        intent_value="List tables",
        intent_type=IntentType.TOOL,
        intent_target="postgres_list_tables",
    ),
]


def tools_for(credentials: dict[str, str]) -> list[Any]:
    """The PostgreSQL tools, or none without host, port, database, user, password."""
    if not all(
        credentials.get(field)
        for field in ("host", "port", "database", "user", "password")
    ):
        return []
    return as_tools(PostgresIntegrationConfiguration(**credentials))


async def create_agent(
    engine: Any, module_id: str, *, credentials: dict[str, str], chat_model: str = ""
) -> Agent:
    tools = tools_for(credentials)
    names = {tool.name for tool in tools}
    return await build_agent(
        engine,
        module_id,
        name=NAME,
        description=DESCRIPTION,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        # A tool intent without its tool would route to nothing.
        intents=[
            i
            for i in INTENTS
            if i.intent_type != IntentType.TOOL or i.intent_target in names
        ],
        chat_model=chat_model,
    )
