from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)
from naas_abi_core.module.Module import BaseModule
from naas_abi_marketplace.applications.google_search import ABIModule

NAME = "Google_Search"
DESCRIPTION = "Search the web using Google Programmable Search Engine."
AVATAR_URL = "https://s3-alpha.figma.com/hub/file/4765445806/10c157d8-1da5-42fd-8143-4dd6df2656ab-cover.png"
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
SUGGESTIONS: list[dict] = [
    {
        "label": "Search the web",
        "value": "Google: ",
    },
    {
        "label": "Search LinkedIn profile",
        "value": "Search LinkedIn profile for:",
    },
    {
        "label": "Search LinkedIn organization",
        "value": "Search LinkedIn organization for:",
    },
]


def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Initialize module
    module: BaseModule = ABIModule.get_instance()
    google_custom_search_api_key = module.configuration.google_custom_search_api_key
    google_custom_search_engine_id = module.configuration.google_custom_search_engine_id

    # Define model
    from naas_abi_marketplace.ai.gemini.models.google_gemini_2_5_flash import model

    # Define tools
    tools: list = []

    # Add Google Programmable Search Engine integration as tool
    from naas_abi_marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
        GoogleProgrammableSearchEngineIntegrationConfiguration,
        as_tools,
    )

    google_programmable_search_engine_integration_config = (
        GoogleProgrammableSearchEngineIntegrationConfiguration(
            api_key=google_custom_search_api_key,
            search_engine_id=google_custom_search_engine_id,
        )
    )

    tools += as_tools(google_programmable_search_engine_integration_config)

    # Add SearchLinkedInProfilePageWorkflow as tool
    from naas_abi_marketplace.applications.google_search.workflows.SearchLinkedInProfilePageWorkflow import (
        SearchLinkedInProfilePageWorkflow,
        SearchLinkedInProfilePageWorkflowConfiguration,
    )

    search_linkedin_profile_page_workflow_config = (
        SearchLinkedInProfilePageWorkflowConfiguration(
            integration_config=google_programmable_search_engine_integration_config
        )
    )
    search_linkedin_profile_page_workflow = SearchLinkedInProfilePageWorkflow(
        search_linkedin_profile_page_workflow_config
    )
    tools += search_linkedin_profile_page_workflow.as_tools()

    # Add SearchLinkedInOrganizationPageWorkflow as tool
    from naas_abi_marketplace.applications.google_search.workflows.SearchLinkedInOrganizationPageWorkflow import (
        SearchLinkedInOrganizationPageWorkflow,
        SearchLinkedInOrganizationPageWorkflowConfiguration,
    )

    search_linkedin_organization_page_workflow_config = (
        SearchLinkedInOrganizationPageWorkflowConfiguration(
            integration_config=google_programmable_search_engine_integration_config
        )
    )
    search_linkedin_organization_page_workflow = SearchLinkedInOrganizationPageWorkflow(
        search_linkedin_organization_page_workflow_config
    )
    tools += search_linkedin_organization_page_workflow.as_tools()

    # Set intents
    intents: list = [
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
    system_prompt = SYSTEM_PROMPT.replace(
        "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    )

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=system_prompt,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return GoogleSearchAgent(
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


class GoogleSearchAgent(IntentAgent):
    pass
