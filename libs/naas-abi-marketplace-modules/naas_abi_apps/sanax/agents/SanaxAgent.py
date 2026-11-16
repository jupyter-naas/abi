"""Sanax agent: an SDK IntentAgent hosted by the remote ``sanax`` module.

Its query tools are the templatable SPARQL queries of the module's
``ontologies/`` (``naas_abi_apps.common.sparql_templates``), plus ``count_items``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from naas_abi_apps.common.agents import build_agent, tools_prompt
from naas_abi_apps.common.sparql_templates import module_queries, query_tools
from naas_abi_sdk.agents import Agent, Intent, IntentType

logger = logging.getLogger(__name__)

NAME = "Sanax"
DESCRIPTION = "Sanax agent to extract sales navigator data from LinkedIn."
SYSTEM_PROMPT = """
<role>
You are Sanax, an AI agent specialized in extracting and analyzing LinkedIn Sales Navigator data.
</role>

<objective>
Help users gain insights from LinkedIn Sales Navigator data by providing accurate information and analysis.
</objective>

<context>
You receive messages from users or the supervisor agent.
</context>

<tasks>
- Extract relevant information from LinkedIn Sales Navigator data using available tools
- Answer specific questions about people, companies, and roles
- Provide quantitative analysis when requested
- Guide users by asking for missing information needed to use tools effectively
</tasks>

<tools>
- count_items: Count of items returned by another tool.
[TOOLS]
</tools>

<operating_guidelines>
- Find appropriate tool to answer the question.
- Make sure user provide all necessary arguments to the tool, otherwise ask for the missing arguments.
- Use tool to answer questions
- If user is asking a quantitative question, use the count_items tool to answer the question.
- Present clear and concise answer:
    - If url is provided, return it in markdown: [URL](url).
    - If an image is provided, return it in markdown: ![Image](url).
</operating_guidelines>

<constraints>
- Only use tools to answer questions.
- Never user your internal knowledge to answer the question.
</constraints>
"""

INTENTS: list[Intent] = [
    Intent(
        intent_value="what do you know about {person}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_information_about_person",
    ),
    Intent(
        intent_value="tell me about {person}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_information_about_person",
    ),
    Intent(
        intent_value="who is {person}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_information_about_person",
    ),
    Intent(
        intent_value="search for people named {name}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_search_persons_by_name",
    ),
    Intent(
        intent_value="find people with name {name}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_search_persons_by_name",
    ),
    Intent(
        intent_value="show me people whose names start with {prefix}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_persons_by_name_prefix",
    ),
    Intent(
        intent_value="who works at {company}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_company_employees",
    ),
    Intent(
        intent_value="show me employees at {company}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_company_employees",
    ),
    Intent(
        intent_value="search for companies named {name}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_search_companies_by_name",
    ),
    Intent(
        intent_value="find companies with name {name}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_search_companies_by_name",
    ),
    Intent(
        intent_value="how many people work at {company}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_count_people_working_for_company",
    ),
    Intent(
        intent_value="who has the position of {position}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_people_holding_position",
    ),
    Intent(
        intent_value="show me people with title {position}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_people_holding_position",
    ),
    Intent(
        intent_value="find people who are {position}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_people_holding_position",
    ),
    Intent(
        intent_value="who are the people in {location}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_people_located_in_location",
    ),
    Intent(
        intent_value="show me people located in {location}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_people_located_in_location",
    ),
    Intent(
        intent_value="how many people are in {location}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_count_people_located_in_location",
    ),
    Intent(
        intent_value="count people in {location}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_count_people_located_in_location",
    ),
    Intent(
        intent_value="who started their job most recently",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_people_with_most_recent_job_starts",
    ),
    Intent(
        intent_value="show me recent job starts",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_people_with_most_recent_job_starts",
    ),
    Intent(
        intent_value="who started their job longest ago",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_people_with_longest_job_starts",
    ),
    Intent(
        intent_value="show me oldest job starts",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_people_with_longest_job_starts",
    ),
    Intent(
        intent_value="who has worked the longest for a {company}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_people_with_longest_tenure",
    ),
    Intent(
        intent_value="show me people with longest tenure for a {company}",
        intent_type=IntentType.TOOL,
        intent_target="sanax_get_people_with_longest_tenure",
    ),
]

PACKAGE_DIR = Path(__file__).resolve().parents[1]


def count_items_tool(tools: list[Any]) -> Any:
    """``count_items``: call another tool and count what it returns."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    by_name = {tool.name: tool for tool in tools}

    class CountSchema(BaseModel):
        function_name: str = Field(description="The name of the function to call")
        function_args: dict[str, Any] | None = Field(
            None, description="Arguments to pass to the target function"
        )

    async def count_items(
        function_name: str, function_args: dict[str, Any] | None = None
    ) -> int:
        if function_name not in by_name:
            logger.error(
                "count_items: no tool %s (have %s)", function_name, sorted(by_name)
            )
            return 0
        try:
            result = await by_name[function_name].ainvoke(function_args or {})
        except Exception as exc:  # noqa: BLE001 - as in-engine: 0 on failure
            logger.error("count_items: %s", exc)
            return 0
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except ValueError:
                return 1
        if result is None:
            return 0
        return len(result) if isinstance(result, list | dict) else 1

    return StructuredTool(
        name="count_items",
        description="Count the number of results returned by another tool by calling it and counting the returned items.",
        coroutine=count_items,
        args_schema=CountSchema,
    )


def build_tools(triple_store: Any) -> list[Any]:
    templates = query_tools(module_queries(PACKAGE_DIR), triple_store)
    return [count_items_tool(templates), *templates]


async def create_agent(engine: Any, module_id: str, *, chat_model: str = "") -> Agent:
    tools = build_tools(engine.services.triple_store)
    names = {tool.name for tool in tools}
    return await build_agent(
        engine,
        module_id,
        name=NAME,
        description=DESCRIPTION,
        system_prompt=tools_prompt(SYSTEM_PROMPT, tools),
        tools=tools,
        intents=[
            i
            for i in INTENTS
            if i.intent_type != IntentType.TOOL or i.intent_target in names
        ],
        chat_model=chat_model,
    )
