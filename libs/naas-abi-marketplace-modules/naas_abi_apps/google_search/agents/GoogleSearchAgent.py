"""Google Search agent: an SDK IntentAgent hosted by the remote ``google_search`` module."""

from __future__ import annotations

from typing import Any

from naas_abi_apps.common.agents import build_agent, tools_prompt
from naas_abi_apps.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegrationConfiguration,
    as_tools,
)
from naas_abi_sdk.agents import Agent, Intent, IntentType

NAME = "Google_Search"
DESCRIPTION = "Search the web using Google Programmable Search Engine."
SYSTEM_PROMPT = """<role>
You are Google Search, an expert agent with capabilities to retrieve information from the web using Google Programmable Search Engine.
</role>

<objective>
Your primary mission is to help users find information on the web by performing targeted searches and presenting results in a clear, organized format.
</objective>

<tools>
[TOOLS]
</tools>

<tasks>
- Perform web searches (Google it) using Google Programmable Search Engine tools.
- Explore the results by extracting the content from the URL.
- Present search results with title, link, snippet, and thumbnail images in markdown format.
</tasks>

<operating_guidelines>
- Find if specific tool exists to perform the search. If it does, use it. If it doesn't, use googlesearch_query tool.
- If user need to explore result, use googlesearch_extract_content_from_url tool to extract the content from the URL.
</operating_guidelines>

<constraints>
- Be concise and to the point
- Always present search results in a clear, readable format
- Include thumbnails when available
- Cite sources and explain search methodology
- Display images in markdown format: ![Image](url)
</constraints>
"""

INTENTS: list[Intent] = [
    Intent(
        intent_value="Search the web",
        intent_type=IntentType.TOOL,
        intent_target="googlesearch_query",
    ),
    Intent(
        intent_value="Google it",
        intent_type=IntentType.TOOL,
        intent_target="googlesearch_query",
    ),
    Intent(
        intent_value="Find information about",
        intent_type=IntentType.TOOL,
        intent_target="googlesearch_query",
    ),
    Intent(
        intent_value="Search for a LinkedIn profile",
        intent_type=IntentType.TOOL,
        intent_target="googlesearch_search_linkedin_profile_page",
    ),
    Intent(
        intent_value="Find LinkedIn profile",
        intent_type=IntentType.TOOL,
        intent_target="googlesearch_search_linkedin_profile_page",
    ),
    Intent(
        intent_value="Search for a LinkedIn organization",
        intent_type=IntentType.TOOL,
        intent_target="googlesearch_search_linkedin_organization_page",
    ),
    Intent(
        intent_value="Find LinkedIn company",
        intent_type=IntentType.TOOL,
        intent_target="googlesearch_search_linkedin_organization_page",
    ),
    Intent(
        intent_value="Search for LinkedIn company",
        intent_type=IntentType.TOOL,
        intent_target="googlesearch_search_linkedin_organization_page",
    ),
]


def workflow_tools(profile: Any, organization: Any) -> list[Any]:
    """The two LinkedIn page searches as tools, under their in-engine names."""
    from langchain_core.tools import StructuredTool
    from naas_abi_apps.google_search.workflows.SearchLinkedInOrganizationPageWorkflow import (
        SearchLinkedInOrganizationPageWorkflowParameters,
    )
    from naas_abi_apps.google_search.workflows.SearchLinkedInProfilePageWorkflow import (
        SearchLinkedInProfilePageWorkflowParameters,
    )

    async def search_profile(
        profile_name: str, organization_name: str | None = None
    ) -> Any:
        return await profile.run(
            SearchLinkedInProfilePageWorkflowParameters(
                profile_name=profile_name, organization_name=organization_name
            )
        )

    async def search_organization(organization_name: str) -> Any:
        return await organization.run(
            SearchLinkedInOrganizationPageWorkflowParameters(
                organization_name=organization_name
            )
        )

    return [
        StructuredTool(
            name="googlesearch_search_linkedin_profile_page",
            description="Search for LinkedIn profile page URL using Google Programmable Search Engine",
            coroutine=search_profile,
            args_schema=SearchLinkedInProfilePageWorkflowParameters,
        ),
        StructuredTool(
            name="googlesearch_search_linkedin_organization_page",
            description="Search for LinkedIn organization page URL using Google Programmable Search Engine",
            coroutine=search_organization,
            args_schema=SearchLinkedInOrganizationPageWorkflowParameters,
        ),
    ]


async def create_agent(
    engine: Any,
    module_id: str,
    *,
    integration: GoogleProgrammableSearchEngineIntegrationConfiguration | None,
    extra_tools: list[Any],
    chat_model: str = "",
) -> Agent:
    """No credentials (``integration`` None): the agent loads without search tools,
    as the in-engine one did."""
    tools = (as_tools(integration) + extra_tools) if integration is not None else []
    names = {tool.name for tool in tools}
    return await build_agent(
        engine,
        module_id,
        name=NAME,
        description=DESCRIPTION,
        system_prompt=tools_prompt(SYSTEM_PROMPT, tools),
        tools=tools,
        intents=[i for i in INTENTS if i.intent_target in names],
        chat_model=chat_model,
    )
