from langchain_openai import ChatOpenAI
from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from fastapi import APIRouter
from typing import Optional
from pydantic import SecretStr
from enum import Enum
from src import secret

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
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get('OPENAI_API_KEY'))
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=SYSTEM_PROMPT
        )
    
    # Set shared state
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    tools: list = []
    
    # Add integration based on available credentials
    from src.marketplace.applications.postgres.integrations.PostgresIntegration import PostgresIntegrationConfiguration
    from src.marketplace.applications.postgres.integrations.PostgresIntegration import as_tools
    if all(secret.get(key) for key in ['POSTGRES_HOST', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']):    
        integration_config = PostgresIntegrationConfiguration(
            host=secret.get('POSTGRES_HOST'),
            port=int(secret.get('POSTGRES_PORT', "5432")),
            database=secret.get('POSTGRES_DB'),
            user=secret.get('POSTGRES_USER'),
            password=secret.get('POSTGRES_PASSWORD')
        )
        tools += as_tools(integration_config)

    intents: list = [
        Intent(intent_value="Execute a SQL query", intent_type=IntentType.TOOL, intent_target="postgres_query"),
        Intent(intent_value="Show database schema", intent_type=IntentType.TOOL, intent_target="postgres_schema"),
        Intent(intent_value="List tables", intent_type=IntentType.TOOL, intent_target="postgres_tables"),
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
        memory=None
    )

class PostgresAgent(IntentAgent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "postgres", 
        name: str = NAME, 
        description: str = "API endpoints to call the PostgreSQL assistant completion.", 
        description_stream: str = "API endpoints to call the PostgreSQL assistant stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        ) 