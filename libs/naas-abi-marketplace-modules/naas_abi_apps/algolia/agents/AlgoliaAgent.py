"""Algolia agent: an SDK IntentAgent hosted by the remote ``algolia`` module."""

from __future__ import annotations

from typing import Any

from naas_abi_apps.algolia.integrations.AlgoliaIntegration import (
    AlgoliaIntegrationConfiguration,
    as_tools,
)
from naas_abi_apps.common.agents import build_agent, tools_prompt
from naas_abi_sdk.agents import Agent, Intent, IntentType

NAME = "Algolia"
DESCRIPTION = "An Agent that helps you interact with Algolia search services, including searching indexes and managing records."
SYSTEM_PROMPT = """<role>
You are Algolia, an expert search and indexing specialist. You possess deep expertise in:
</role>

<objective>
Help users interact with Algolia search services, including searching indexes and managing records.
</objective>

<context>
You operate within a secure environment with authenticated access to Algolia services through configured API credentials.
</context>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Verify you have access to the tools, otherwise ask the user to set their Algolia credentials (ALGOLIA_API_KEY, ALGOLIA_APPLICATION_ID) as engine secrets
- Always confirm the index name before performing operations
- For searches, try to understand the user's intent to form the most effective query
- When adding records, ensure they follow the correct format for Algolia indexing

<constraints>
- Be concise and to the point
- Maintain professional tone
- Always cite data sources and explain methodology used
</constraints>
"""

INTENTS: list[Intent] = [
    Intent(
        intent_value="Search in Algolia index",
        intent_type=IntentType.TOOL,
        intent_target="algolia_search_index",
    ),
    Intent(
        intent_value="Add records to index",
        intent_type=IntentType.TOOL,
        intent_target="algolia_update_records",
    ),
    Intent(
        intent_value="List Algolia indexes",
        intent_type=IntentType.TOOL,
        intent_target="algolia_list_indexes",
    ),
]


def tools_for(credentials: dict[str, str]) -> list[Any]:
    """The Algolia tools, or none without api_key, app_id."""
    if not all(credentials.get(field) for field in ("api_key", "app_id")):
        return []
    return as_tools(AlgoliaIntegrationConfiguration(**credentials))


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
        system_prompt=tools_prompt(SYSTEM_PROMPT, tools),
        tools=tools,
        # A tool intent without its tool would route to nothing.
        intents=[
            i
            for i in INTENTS
            if i.intent_type != IntentType.TOOL or i.intent_target in names
        ],
        chat_model=chat_model,
    )
