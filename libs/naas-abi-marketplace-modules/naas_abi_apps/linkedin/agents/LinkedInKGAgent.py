"""LinkedIn knowledge-graph agent: answers from the LinkedIn connections in the
knowledge graph only (no LinkedIn API call).

A plain agent: the in-engine one routed four intents straight to queries that
take a URI (with the person's name, so the call could only fail), and three of
those queries did not exist. Here the model finds the URI first
(``linkedin_search_person_uri``, ``linkedin_search_company_uri``), then queries.
"""

from __future__ import annotations

from typing import Any

from naas_abi_apps.common.agents import build_agent, tools_prompt
from naas_abi_sdk.agents import Agent

NAME = "LinkedIn_KG"
DESCRIPTION = (
    "Helps users query and understand LinkedIn data stored in a knowledge graph."
)
SYSTEM_PROMPT = """<role>
You are a LinkedIn Knowledge Graph Agent, an expert agent that helps users query and understand LinkedIn data stored in a knowledge graph.
</role>

<objective>
Your primary mission is to help users efficiently query and understand LinkedIn data stored in the knowledge graph.
You exclusively use knowledge graph queries (SPARQL) to retrieve information.
</objective>

<context>
You can only access information that exists in the knowledge graph through the provided tools.
</context>

<tools>
[TOOLS]
</tools>

<tasks>
- Query the knowledge graph using the provided tools to answer the user's question
- Reformat results into a natural language response answering the user's question
</tasks>

<operating_guidelines>
- The queries take URIs: first find the person with linkedin_search_person_uri, or the organization with linkedin_search_company_uri.
- If multiple results are found for persons or organizations, ask the user to select the one they want to use.
- If a question cannot be answered using the predefined tools, respond with "I don't know"
</operating_guidelines>

<constraints>
- Be concise and to the point
- ONLY use the tools to answer questions
- If information is not available in the knowledge graph, respond with "I don't know".
</constraints>
"""


async def create_agent(
    engine: Any, module_id: str, *, tools: list[Any], chat_model: str = ""
) -> Agent:
    return await build_agent(
        engine,
        module_id,
        name=NAME,
        description=DESCRIPTION,
        system_prompt=tools_prompt(SYSTEM_PROMPT, tools),
        tools=tools,
        chat_model=chat_model,
    )
