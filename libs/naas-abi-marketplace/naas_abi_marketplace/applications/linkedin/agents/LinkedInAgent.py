from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
    IntentType,
)


class LinkedInAgent(IntentAgent):
    name: str = "LinkedIn"
    description: str = "Access LinkedIn through your account."
    avatar_url: str = "https://content.linkedin.com/content/dam/me/business/en-us/amp/brand-site/v2/bg/LI-Bug.svg.original.svg"
    system_prompt: str = """<role>
You are a LinkedIn Professional Agent, an expert assistant specialized in LinkedIn data extraction, analysis, and professional networking insights.
</role>

<objective>
Your primary mission is to help users efficiently access, analyze, and understand LinkedIn data including company profiles, personal profiles, posts, comments, and engagement metrics.
You transform raw LinkedIn data into actionable insights for professional networking, business intelligence, and social media strategy.
You help users dig into LinkedIn data extraction to find the most relevant information for their needs.
</objective>

<context>
You have access to profile of the user: [LINKEDIN_PROFILE_URL].
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

- Get mutual connections:
1. Use Google Search to find the profile URL and validate the URL is correct with the user.
2. Always return the number of mutual connections and the first 10 profiles after using the linkedin_get_mutual_connexions tool:
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
    suggestions: list[str] = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "LinkedInAgent":
        from naas_abi_core.engine.context import get_default_model_registry
        from naas_abi_core.modules.templatablesparqlquery import (
            ABIModule as TemplatableSparqlQueryABIModule,
        )
        from naas_abi_marketplace.applications.google_search import (
            ABIModule as GoogleSearchABIModule,
        )
        from naas_abi_marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
            GoogleProgrammableSearchEngineIntegrationConfiguration,
        )
        from naas_abi_marketplace.applications.google_search.workflows.SearchLinkedInOrganizationPageWorkflow import (
            SearchLinkedInOrganizationPageWorkflow,
            SearchLinkedInOrganizationPageWorkflowConfiguration,
        )
        from naas_abi_marketplace.applications.google_search.workflows.SearchLinkedInProfilePageWorkflow import (
            SearchLinkedInProfilePageWorkflow,
            SearchLinkedInProfilePageWorkflowConfiguration,
        )
        from naas_abi_marketplace.applications.linkedin import ABIModule
        from naas_abi_marketplace.applications.linkedin.integrations.LinkedInIntegration import (
            LinkedInIntegrationConfiguration,
            as_tools,
        )
        from naas_abi_marketplace.applications.naas import ABIModule as NaasABIModule
        from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
            NaasIntegrationConfiguration,
        )

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        module = ABIModule.get_instance()
        li_at = module.configuration.li_at
        JSESSIONID = module.configuration.JSESSIONID
        linkedin_profile_url = module.configuration.linkedin_profile_url

        google_search_module = GoogleSearchABIModule.get_instance()
        google_custom_search_api_key = google_search_module.configuration.google_custom_search_api_key
        google_custom_search_engine_id = google_search_module.configuration.google_custom_search_engine_id

        naas_api_key = NaasABIModule.get_instance().configuration.naas_api_key
        naas_integration_config = NaasIntegrationConfiguration(
            api_key=naas_api_key,
        )

        tools: list = []

        linkedin_integration_config = LinkedInIntegrationConfiguration(
            li_at=li_at,
            JSESSIONID=JSESSIONID,
            linkedin_url=linkedin_profile_url,
            naas_integration_config=naas_integration_config,
        )
        tools += as_tools(linkedin_integration_config)

        google_programmable_search_engine_integration_config = (
            GoogleProgrammableSearchEngineIntegrationConfiguration(
                api_key=google_custom_search_api_key,
                search_engine_id=google_custom_search_engine_id,
            )
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

        search_linkedin_organization_page_workflow_config = (
            SearchLinkedInOrganizationPageWorkflowConfiguration(
                integration_config=google_programmable_search_engine_integration_config
            )
        )
        search_linkedin_organization_page_workflow = SearchLinkedInOrganizationPageWorkflow(
            search_linkedin_organization_page_workflow_config
        )
        tools += search_linkedin_organization_page_workflow.as_tools()

        linkedin_tools = [
            "linkedin_search_connections_by_person_name",
            "linkedin_count_connections_by_person",
            "linkedin_get_connection_information",
            "linkedin_search_email_address_by_person_uri",
        ]
        sparql_query_tools_list = TemplatableSparqlQueryABIModule.get_instance().get_tools(
            linkedin_tools
        )
        tools += sparql_query_tools_list

        intents: list = [
            Intent(
                intent_value="Who am I?",
                intent_type=IntentType.TOOL,
                intent_target="linkedin_get_profile_top_card",
            ),
            Intent(
                intent_value="Search Google for a LinkedIn organization",
                intent_type=IntentType.TOOL,
                intent_target="googlesearch_search_linkedin_organization_page",
            ),
            Intent(
                intent_value="Search Google for a LinkedIn profile",
                intent_type=IntentType.TOOL,
                intent_target="googlesearch_search_linkedin_profile_page",
            ),
            Intent(
                intent_value="www.linkedin.com/in/...",
                intent_type=IntentType.TOOL,
                intent_target="linkedin_get_profile_top_card",
            ),
            Intent(
                intent_value="www.linkedin.com/company/...",
                intent_type=IntentType.TOOL,
                intent_target="linkedin_get_organization_info",
            ),
            Intent(
                intent_value="www.linkedin.com/showcase/...",
                intent_type=IntentType.TOOL,
                intent_target="linkedin_get_organization_info",
            ),
            Intent(
                intent_value="www.linkedin.com/school/...",
                intent_type=IntentType.TOOL,
                intent_target="linkedin_get_organization_info",
            ),
            Intent(
                intent_value="What is this person's skills?",
                intent_type=IntentType.TOOL,
                intent_target="linkedin_get_profile_skills",
            ),
            Intent(
                intent_value="Who is connected with this person?",
                intent_type=IntentType.TOOL,
                intent_target="linkedin_get_mutual_connexions",
            ),
            Intent(
                intent_value="Is this person in my LinkedIn network?",
                intent_type=IntentType.TOOL,
                intent_target="linkedin_get_mutual_connexions",
            ),
        ]

        system_prompt = cls.system_prompt.replace(
            "[TOOLS]", "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
        ).replace("[LINKEDIN_PROFILE_URL]", linkedin_profile_url)

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            embedding_model=embedding_model,
            tools=tools,
            agents=[],
            intents=intents,
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
