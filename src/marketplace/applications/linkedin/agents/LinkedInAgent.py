from abi.services.agent.IntentAgent import (
    IntentAgent,
    Intent,
    IntentType,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional
from src import secret

NAME = "LinkedIn"
DESCRIPTION = "Access LinkedIn through your account."
AVATAR_URL = "https://content.linkedin.com/content/dam/me/business/en-us/amp/brand-site/v2/bg/LI-Bug.svg.original.svg"
SYSTEM_PROMPT = f"""<role>
You are a LinkedIn Professional Agent, an expert assistant specialized in LinkedIn data extraction, analysis, and professional networking insights. 
</role>

<objective>
Your primary mission is to help users efficiently access, analyze, and understand LinkedIn data including company profiles, personal profiles, posts, comments, and engagement metrics. 
You transform raw LinkedIn data into actionable insights for professional networking, business intelligence, and social media strategy. 
You help users dig into LinkedIn data extraction to find the most relevant information for their needs.
</objective>

<context>
You have access to profile of the user: {secret.get('LINKEDIN_PROFILE_URL')}.
</context>

<tools>
[TOOLS]
</tools>

<tasks>
- Search Google for a LinkedIn organization or profile URL using the tools provided.
- Retrieve profile information
- Retrieve organization information
- Retrieve post statistics, comments, and reactions
- For any other request not covered by the tools, just say you don't have access to the feature but the user can contact support@naas.ai to get access to the feature.
</tasks>

<operating_guidelines>
- Google Search: 
1. If a LinkedIn URL is not provided for a person or organization, use provided tools to find them
2. Present the results with title, link, snippet, and thumbnail image in markdown format:
```
- [title](link) - [snippet] ![Thumbnail](thumbnail)
- ...
```
3. Ask the user to validate the URL is correct.
4. If the URL is correct, use the tool to get the information.
5. If the URL is not correct, say you don't have access to the feature but the user can contact support@naas.ai to get access to the feature.

- LinkedIn profile posts feed:
1. Use the linkedin_get_profile_id tool to get the profile ID first before using the toollinkedin_get_profile_posts_feed

- Get mutual connections:
1. Use Google Search to find the profile URL and validate the URL is correct with the user.
2. Use the linkedin_get_profile_id tool to get the profile ID.
3. If no company ID or URL is provided, pass an empty string = "". If provided, use the linkedin_get_organization_id tool to get the organization ID.
4. Always return the number of mutual connections and the first 10 profiles after using the linkedin_get_mutual_connexions tool:
```
I found x mutual connections with [person name]. 

Here are the first 10 profiles:
- [Profile 1](https://www.linkedin.com/in/profile-1)
- [Profile 2](https://www.linkedin.com/in/profile-2)
- [Profile 3](https://www.linkedin.com/in/profile-3)

Would you like to filter the results on their current organization [organization name] to reduce the number of results?
...
```
4. Propose to filter the results on a company to reduce the number of results.
</operating_guidelines>

<constraints>
- Be concise and to the point
- Only work with valid LinkedIn URLs (company, profile, or post URLs)
- Respect LinkedIn's data usage policies and rate limits
- Maintain professional tone
- Always cite data sources and explain methodology used
- Display image in markdown format: ![Image](url).
</constraints>
"""

SUGGESTIONS: list[str] = []

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None,
) -> IntentAgent:
    # Set model
    from src.core.chatgpt.models.gpt_4_1_mini import model
    
    # Set tools
    from src.marketplace.applications.linkedin.integrations.LinkedInIntegration import LinkedInIntegrationConfiguration
    tools: list = []
    li_at = "AQEDARCNSioE2dAnAAABmbhM51IAAAGapfpA-E0AU2nAbiSPq8u-qEfMlklIUKXmsdvuZQpP0pflN4p-jHwYVq57YTzHq9Xivussd2HPcqVVQX8BDKks6kiMN_u3fNNkYJTfW041fEQMJDhLJ60SVjSC" or secret.get('li_at')
    JSESSIONID = "ajax:7698090324817961474" or secret.get('JSESSIONID')
    linkedin_integration_config = LinkedInIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID)
    from src.marketplace.applications.linkedin.integrations import LinkedInIntegration
    tools += LinkedInIntegration.as_tools(linkedin_integration_config)

    from src.marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
        GoogleProgrammableSearchEngineIntegrationConfiguration
    )
    google_programmable_search_engine_integration_config = GoogleProgrammableSearchEngineIntegrationConfiguration(
        api_key=secret.get('GOOGLE_CUSTOM_SEARCH_API_KEY'),
        search_engine_id=secret.get('GOOGLE_CUSTOM_SEARCH_ENGINE_ID')
    )

    from src.marketplace.applications.google_search.workflows.SearchLinkedInProfilePageWorkflow import (
        SearchLinkedInProfilePageWorkflowConfiguration,
        SearchLinkedInProfilePageWorkflow
    )
    search_linkedin_profile_page_workflow_config = SearchLinkedInProfilePageWorkflowConfiguration(
        integration_config=google_programmable_search_engine_integration_config
    )
    search_linkedin_profile_page_workflow = SearchLinkedInProfilePageWorkflow(search_linkedin_profile_page_workflow_config)
    tools += search_linkedin_profile_page_workflow.as_tools()

    from src.marketplace.applications.google_search.workflows.SearchLinkedInOrganizationPageWorkflow import (
        SearchLinkedInOrganizationPageWorkflowConfiguration,
        SearchLinkedInOrganizationPageWorkflow
    )
    search_linkedin_organization_page_workflow_config = SearchLinkedInOrganizationPageWorkflowConfiguration(
        integration_config=google_programmable_search_engine_integration_config
    )
    search_linkedin_organization_page_workflow = SearchLinkedInOrganizationPageWorkflow(search_linkedin_organization_page_workflow_config)
    tools += search_linkedin_organization_page_workflow.as_tools()

    # Set intents
    intents: list = [
        Intent(intent_value="Who am I?", intent_type=IntentType.TOOL, intent_target="linkedin_get_profile_top_card"),
        Intent(intent_value="Search Google for a LinkedIn organization", intent_type=IntentType.TOOL, intent_target="googlesearch_search_linkedin_organization_page"),
        Intent(intent_value="Search Google for a LinkedIn profile", intent_type=IntentType.TOOL, intent_target="googlesearch_search_linkedin_profile_page"),
        Intent(intent_value="www.linkedin.com/in/...", intent_type=IntentType.TOOL, intent_target="linkedin_get_profile_top_card"),
        Intent(intent_value="www.linkedin.com/company/...", intent_type=IntentType.TOOL, intent_target="linkedin_get_organization_info"),
        Intent(intent_value="www.linkedin.com/showcase/...", intent_type=IntentType.TOOL, intent_target="linkedin_get_organization_info"),
        Intent(intent_value="www.linkedin.com/school/...", intent_type=IntentType.TOOL, intent_target="linkedin_get_organization_info"),
        Intent(intent_value="What is this person's skills?", intent_type=IntentType.TOOL, intent_target="linkedin_get_profile_skills"),
        Intent(intent_value="Who is connected with this person?", intent_type=IntentType.TOOL, intent_target="linkedin_get_mutual_connexions"),
        Intent(intent_value="Is this person in my LinkedIn network?", intent_type=IntentType.TOOL, intent_target="linkedin_get_mutual_connexions"),
    ]
    system_prompt = SYSTEM_PROMPT.replace("[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools]))
    
    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(
            system_prompt=system_prompt,
        )
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

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
    pass
