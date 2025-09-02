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

NAME = "LinkedIn"
DESCRIPTION = "Access LinkedIn through your account."
MODEL = "gpt-4o"
TEMPERATURE = 0
AVATAR_URL = "https://content.linkedin.com/content/dam/me/business/en-us/amp/brand-site/v2/bg/LI-Bug.svg.original.svg"
SYSTEM_PROMPT = """
## Role
You are a LinkedIn Professional Agent, an expert assistant specialized in LinkedIn data extraction, analysis, and professional networking insights. 
You have deep expertise in LinkedIn's data structures, professional networking patterns, and social media analytics.

## Objective
Your primary mission is to help users efficiently access, analyze, and understand LinkedIn data including company profiles, personal profiles, posts, comments, and engagement metrics. 
You transform raw LinkedIn data into actionable insights for professional networking, business intelligence, and social media strategy.

## Context
You operate within a secure environment with authenticated access to LinkedIn's internal APIs through cookie-based authentication (li_at and JSESSIONID). 

## Tools
- `linkedin_get_organization_info`: Get comprehensive company information including details, metrics, and metadata
- `linkedin_get_profile_view`: Get detailed profile view data including experience, education, and connections
- `linkedin_get_post_stats`: Get post performance metrics (views, likes, shares, comments count)
- `linkedin_get_post_comments`: Get all comments and replies for a specific post
- `linkedin_get_post_reactions`: Get all reactions (likes, celebrates, supports, etc.) for a specific post
- `linkedin_json_cleaner`: Clean JSON data to make it LLM-friendly by removing unnecessary fields, flattening structures, and extracting image URLs
- `googlesearch_linkedin_organization`: Search Google for a LinkedIn organization
- `googlesearch_linkedin_profile`: Search Google for a LinkedIn profile

## Tasks
- Search Google for a LinkedIn organization or profile
- Retrieve profile information
- Retrieve organization information
- Retrieve post statistics, comments, and reactions
- For any other request not covered by the tools, just say you don't have access to the feature but the user can contact support@naas.ai to get access to the feature.

## Operating Guidelines
- If LinkedIn URL is not provided, use `googlesearch_linkedin_organization` or `googlesearch_linkedin_profile` to search Google for a LinkedIn organization or profile.
If multiple results are found, ask the user to select the correct one.
- Get data from LinkedIn using the tools provided
- Use `linkedin_json_cleaner` tool to clean the JSON data before using it
- Provide the data in a clear, professional format with context and explanations

## Constraints
- Be concise and to the point
- Only work with valid LinkedIn URLs (company, profile, or post URLs)
- Respect LinkedIn's data usage policies and rate limits
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
    
    # Set model
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")
    
    from src.marketplace.modules.applications.naas.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
    from src.marketplace.modules.applications.linkedin.integrations.LinkedInIntegration import LinkedInIntegrationConfiguration

    tools: list = []
    naas_api_key = secret.get('NAAS_API_KEY')
    if naas_api_key:
        naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)
        li_at = NaasIntegration(naas_integration_config).get_secret('li_at').get('secret').get('value')
        JSESSIONID = NaasIntegration(naas_integration_config).get_secret('JSESSIONID').get('secret').get('value')
        if li_at and JSESSIONID:
            linkedin_integration_config = LinkedInIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID)
            from src.marketplace.modules.applications.linkedin.integrations import LinkedInIntegration
            tools += LinkedInIntegration.as_tools(linkedin_integration_config)

            from src.marketplace.modules.applications.linkedin.workflows.LinkedInJSONCleanerWorkflow import (
                LinkedInJSONCleanerWorkflow, 
                LinkedInJSONCleanerWorkflowConfiguration
            )
            tools += LinkedInJSONCleanerWorkflow(LinkedInJSONCleanerWorkflowConfiguration()).as_tools()

            from src.marketplace.modules.applications.google_search.integrations.GoogleSearchIntegration import GoogleSearchIntegrationConfiguration
            from src.marketplace.modules.applications.google_search.integrations import GoogleSearchIntegration
            google_search_integration_config = GoogleSearchIntegrationConfiguration()
            tools += GoogleSearchIntegration.as_tools(google_search_integration_config)

    intents: list = [
        Intent(intent_value="Search Google for a LinkedIn organization", intent_type=IntentType.TOOL, intent_target="googlesearch_linkedin_organization"),
        Intent(intent_value="Search Google for a LinkedIn profile", intent_type=IntentType.TOOL, intent_target="googlesearch_linkedin_profile"),
        Intent(intent_value="www.linkedin.com/in/...", intent_type=IntentType.TOOL, intent_target="linkedin_get_profile_view"),
        Intent(intent_value="www.linkedin.com/company/...", intent_type=IntentType.TOOL, intent_target="linkedin_get_organization_info"),
        Intent(intent_value="www.linkedin.com/showcase/...", intent_type=IntentType.TOOL, intent_target="linkedin_get_organization_info"),
        Intent(intent_value="www.linkedin.com/school/...", intent_type=IntentType.TOOL, intent_target="linkedin_get_organization_info"),
        Intent(intent_value="Who reacted to this post?", intent_type=IntentType.TOOL, intent_target="linkedin_get_post_reactions"),
        Intent(intent_value="Who commented on this post?", intent_type=IntentType.TOOL, intent_target="linkedin_get_post_comments"),
    ]

    return LinkedInAgent(
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

class LinkedInAgent(IntentAgent):
    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = NAME, 
        name: str = NAME.capitalize().replace("_", " "), 
        description: str = "API endpoints to call the LinkedIn agent completion.", 
        description_stream: str = "API endpoints to call the LinkedIn agent stream completion.",
        tags: Optional[list[str | Enum]] = None,
    ) -> None:
        if tags is None:
            tags = []
        return super().as_api(
            router, route_name, name, description, description_stream, tags
        )
