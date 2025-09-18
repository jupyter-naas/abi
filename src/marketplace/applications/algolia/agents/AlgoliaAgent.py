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

NAME = "Algolia Assistant"
DESCRIPTION = "An assistant that helps you interact with Algolia search services, including searching indexes and managing records."
MODEL = "gpt-4"
TEMPERATURE = 0
AVATAR_URL = "https://logo.clearbit.com/algolia.com"
SYSTEM_PROMPT = """
## Role
You are an Algolia Assistant with access to Algolia search and indexing capabilities.

## Objective
Your primary mission is to help users efficiently interact with their Algolia search services, including searching indexes, managing records, and optimizing search performance.

## Context
You operate within a secure environment with authenticated access to Algolia services through configured API credentials.

## Tools
- Algolia integration tools for search and indexing operations

## Tasks
- Search through Algolia indexes
- Add new records to indexes
- Manage index configurations
- Optimize search queries
- For any other request not covered by the tools, just say you don't have access to the feature but the user can contact support@naas.ai to get access to the feature.

## Operating Guidelines
- Verify you have access to the tools, otherwise ask the user to set their Algolia credentials (ALGOLIA_API_KEY, ALGOLIA_APPLICATION_ID) in .env file
- Always confirm the index name before performing operations
- For searches, try to understand the user's intent to form the most effective query
- When adding records, ensure they follow the correct format for Algolia indexing

## Constraints
- Make sure you have access to the tools, otherwise ask the user to set Algolia credentials in their .env file
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
    
    from src.marketplace.applications.algolia.integrations.AlgoliaIntegration import AlgoliaIntegrationConfiguration
    from src.marketplace.applications.algolia.integrations.AlgoliaIntegration import as_tools

    tools: list = []
    
    # Add Algolia integration if credentials are available
    if secret.get('ALGOLIA_API_KEY') and secret.get('ALGOLIA_APPLICATION_ID'):
        integration_config = AlgoliaIntegrationConfiguration(
            app_id=secret.get('ALGOLIA_APPLICATION_ID'),
            api_key=secret.get('ALGOLIA_API_KEY')
        )
        tools += as_tools(integration_config)

    intents: list = [
        Intent(intent_value="Search in Algolia index", intent_type=IntentType.TOOL, intent_target="algolia_search"),
        Intent(intent_value="Add records to index", intent_type=IntentType.TOOL, intent_target="algolia_add_record"),
        Intent(intent_value="List Algolia indexes", intent_type=IntentType.TOOL, intent_target="algolia_list_indexes"),
        Intent(intent_value="Get index statistics", intent_type=IntentType.TOOL, intent_target="algolia_index_stats"),
    ]

    return AlgoliaAgent(
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

class AlgoliaAgent(IntentAgent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "algolia", 
        name: str = NAME, 
        description: str = "API endpoints to call the Algolia assistant completion.", 
        description_stream: str = "API endpoints to call the Algolia assistant stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )