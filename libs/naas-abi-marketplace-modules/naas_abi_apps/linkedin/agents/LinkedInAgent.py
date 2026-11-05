"""LinkedIn agent: an SDK IntentAgent hosted by the remote ``linkedin`` module.

Its tools, each only when its credentials are set: the LinkedIn API (session
cookies), the Google searches for LinkedIn pages (the ``google_search``
module's workflows, run in process), and the connection queries on the
knowledge graph.
"""

from __future__ import annotations

from typing import Any

from naas_abi_apps.common.agents import build_agent, tools_prompt
from naas_abi_sdk.agents import Agent, Intent, IntentType

NAME = "LinkedIn"
DESCRIPTION = "Access LinkedIn through your account."
SYSTEM_PROMPT = """<role>
You are a LinkedIn Professional Agent, an expert assistant specialized in LinkedIn data extraction, analysis, and professional networking insights.
</role>

<objective>
Your primary mission is to help users efficiently access, analyze, and understand LinkedIn data including company profiles, personal profiles, posts, comments, and engagement metrics.
You transform raw LinkedIn data into actionable insights for professional networking, business intelligence, and social media strategy.
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
- For any other request not covered by the tools, say you don't have access to the feature; the user can contact support@naas.ai to get access to it.
- If a tool you need is not listed above, say which secret is missing: li_at, JSESSIONID and LINKEDIN_PROFILE_URL for LinkedIn, GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_CUSTOM_SEARCH_ENGINE_ID for the Google searches.
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
5. If the URL is not correct, ask the user for the right URL.

- Get mutual connections:
1. Use Google Search to find the profile URL and validate the URL is correct with the user.
2. Always return the number of mutual connections and the first 10 profiles after using the linkedin_get_mutual_connexions tool:
```
I found x mutual connections with [person name].
Here are the first 10 profiles:
- [Profile 1](profile_url)
- [Profile 2](profile_url)
...
Would you like to filter the results on their current organization [organization name] to reduce the number of results?
```
3. Propose to filter the results on a company to reduce the number of results.
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


def _tool(value: str, target: str) -> Intent:
    return Intent(intent_value=value, intent_type=IntentType.TOOL, intent_target=target)


INTENTS: list[Intent] = [
    _tool("Who am I?", "linkedin_get_profile_top_card"),
    _tool(
        "Search Google for a LinkedIn organization",
        "googlesearch_search_linkedin_organization_page",
    ),
    _tool(
        "Search Google for a LinkedIn profile",
        "googlesearch_search_linkedin_profile_page",
    ),
    _tool("www.linkedin.com/in/...", "linkedin_get_profile_top_card"),
    _tool("www.linkedin.com/company/...", "linkedin_get_organization_info"),
    _tool("www.linkedin.com/showcase/...", "linkedin_get_organization_info"),
    _tool("www.linkedin.com/school/...", "linkedin_get_organization_info"),
    _tool("What is this person's skills?", "linkedin_get_profile_skills"),
    _tool("Who is connected with this person?", "linkedin_get_mutual_connexions"),
    _tool("What are this person's experiences?", "linkedin_get_profile_experience"),
    _tool("What is this person's education?", "linkedin_get_profile_education"),
    _tool("What did this person post recently?", "linkedin_get_profile_posts_feed"),
    _tool("Who commented on this post?", "linkedin_get_post_comments"),
    _tool("Who reacted to this post?", "linkedin_get_post_reactions"),
    _tool("Who reposted this post?", "linkedin_get_post_reposts"),
    _tool("Search people on LinkedIn", "linkedin_search_people"),
    _tool(
        "How many LinkedIn connections does this person have?",
        "linkedin_count_connections_by_person",
    ),
]

# The knowledge-graph queries this agent also has (the KG agent has them all).
QUERIES = (
    "linkedin_count_connections_by_person",
    "linkedin_search_connections_by_person",
    "linkedin_search_connections_by_organization",
    "linkedin_search_person_info",
)


async def create_agent(
    engine: Any,
    module_id: str,
    *,
    tools: list[Any],
    profile_url: str = "",
    chat_model: str = "",
) -> Agent:
    names = {tool.name for tool in tools}
    prompt = tools_prompt(SYSTEM_PROMPT, tools).replace(
        "[LINKEDIN_PROFILE_URL]", profile_url or "not configured"
    )
    return await build_agent(
        engine,
        module_id,
        name=NAME,
        description=DESCRIPTION,
        system_prompt=prompt,
        tools=tools,
        intents=[i for i in INTENTS if i.intent_target in names],
        chat_model=chat_model,
    )
