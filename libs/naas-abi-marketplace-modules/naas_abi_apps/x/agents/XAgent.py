"""X agent: an SDK Agent hosted by the remote ``x`` module.

Port of the in-engine ``XAgent``: same name, description, prompt and tool names.
Its tools:

- the 13 X v2 API tools of ``XIntegration`` (``x_get_user_by_id`` …
  ``x_count_recent_tweets``), only when the bearer token is set
  (``module.bearer_token``, the engine secret ``applications.x/X_BEARER_TOKEN``);
  in-engine they were commented out. ``x_search_recent_tweets`` spends credits,
  so it goes through a spend ledger (``workflows.XSearchRecentTweetsWorkflow``),
  keyed ``agent``, with its own caps (``agent_search_limits``);
- the 14 SPARQL templates of ``ontologies/queries/XSparqlQueries.ttl`` the
  in-engine agent loaded, run on the engine's triple store
  (``common.sparql_templates`` instead of core's ``templatablesparqlquery``).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from naas_abi_apps.common.agents import build_agent
from naas_abi_apps.common.sparql_templates import module_queries, query_tools
from naas_abi_apps.x.integrations.XIntegration import as_tools, x_integration_for
from naas_abi_apps.x.services import logger
from naas_abi_apps.x.workflows.XSearchRecentTweetsWorkflow import (
    BudgetLimits,
    budget_ledger,
    search_with_budget,
)
from naas_abi_sdk import AgentSuggestion
from naas_abi_sdk.agents import Agent

NAME = "X"
DESCRIPTION = (
    "Helps you explore X (Twitter) — users, timelines, follows, "
    "and recent tweet search via the v2 API, plus SPARQL questions "
    "over tweets already ingested into the ABI knowledge graph."
)
# Wikimedia Commons hosts the canonical 2023 X logo (the resolved CDN URL avoids
# the Special:FilePath redirect). For the module's AgentDescriptor (avatar_url).
LOGO_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/"
    "X_logo_2023_original.svg/250px-X_logo_2023_original.svg.png"
)
# The in-engine agent's suggestions, for the module's AgentDescriptor.
SUGGESTIONS = (
    AgentSuggestion(
        "Top liked tweets",
        "Show me the top 10 most liked tweets in the knowledge graph",
        "Rank collected tweets by like count",
    ),
    AgentSuggestion(
        "Most viral tweets",
        "What are the most retweeted tweets?",
        "Rank collected tweets by retweet count",
    ),
    AgentSuggestion(
        "Top engaging tweets",
        "Which tweets drove the most total engagement (likes + retweets + replies + quotes)?",
        "Combined engagement score across all interaction types",
    ),
    AgentSuggestion(
        "Most active authors",
        "Who are the most prolific authors in the knowledge graph?",
        "Rank X users by number of tweets collected",
    ),
    AgentSuggestion(
        "Tweets by handle",
        "Show me all tweets by @",
        "List ingested tweets authored by an X username",
    ),
    AgentSuggestion(
        "Language breakdown",
        "What is the language distribution of collected tweets?",
        "See which languages dominate the ingested dataset",
    ),
    AgentSuggestion(
        "Search by keyword",
        "Find tweets containing the keyword ",
        "Case-insensitive substring search across tweet text",
    ),
)

SYSTEM_PROMPT = """
You are an X (Twitter) Agent with read-only access to the X v2 API via
bearer-token authentication, plus a set of SPARQL tools to query tweets
already ingested into the ABI knowledge graph.

X v2 API tools — use them when the user asks about something **live** on X:
- Look up users by handle (`x_get_user_by_username`) or numeric ID (`x_get_user_by_id`).
- Bulk-fetch up to 100 users in one call (`x_get_users_by_ids`, `x_get_users_by_usernames`).
- Read a user's timeline (`x_get_user_tweets`), mentions (`x_get_user_mentions`),
  and liked tweets (`x_get_user_liked_tweets`).
- Explore a user's follow graph (`x_get_user_followers`, `x_get_user_following`).
- Fetch one or many tweets by ID (`x_get_tweet_by_id`, `x_get_tweets_by_ids`).
- Search tweets from the last 7 days (`x_search_recent_tweets`) using X v2 query
  syntax (operators like `lang:en`, `-is:retweet`, `from:user`).

Graph SPARQL tools — use them when the user asks about tweets **already
collected** in the ABI knowledge graph (i.e. analytical / aggregate
questions over previously-ingested data):
- `find_top_liked_tweets`, `find_top_retweeted_tweets`,
  `find_top_impression_tweets`, `find_top_engaging_tweets` — engagement
  rankings with a `limit`.
- `find_tweets_by_username` — tweets by a specific X handle (`username`,
  with or without `@`; case-insensitive). Prefer this when the user names
  an author by handle.
- `find_tweets_by_author` — tweets by a specific numeric `author_id`.
- `find_tweets_containing_keyword` — substring match on tweet text.
- `find_tweets_in_language` — filter by BCP 47 `lang_code`.
- `find_tweets_since` — tweets created after a UTC `since` timestamp.
- `find_tweet_by_id` — full record for one `tweet_id`.
- `find_top_authors_by_tweet_count` — most prolific authors.
- `find_language_distribution` — tweet count per detected language.
- `find_tweets_by_search_query` — tweets ingested by a specific X v2
  search query (the verbatim `query_string` configured on the
  XOrchestration tweet_ingestion_pipelines).
- `list_ingested_search_queries` — every distinct search query the system
  has ingested tweets for, with the per-query tweet count. Use this to
  answer "what filters / pipelines are we ingesting?" or "list the tweets
  we have ingested" (then call `find_tweets_by_search_query` to drill in).

Routing rules:
- "Most liked / retweeted / viewed / engaging tweets" → graph tool.
- "Top authors / language distribution / tweets containing X / tweets since X" → graph tool.
- "Tweets by @handle / username / what did <handle> post" → graph tool
  (`find_tweets_by_username`). Use `find_tweets_by_author` only when the
  user already gave a numeric author id.
- "What filters are we ingesting / list ingested tweets / tweets for query X" → graph tool
  (`list_ingested_search_queries` then `find_tweets_by_search_query`).
- "What does @handle look like / fetch tweets now / who follows X" → API tool.
- If asked an analytical question and the graph turns out empty, fall back
  to calling `x_search_recent_tweets` and explain that no ingested data
  was available.

Operating guidelines:
- Strip any leading `@` from handles before passing them as `username`.
- When an X v2 endpoint needs a numeric `user_id`, resolve it first with
  `x_get_user_by_username` unless the user already provided an ID.
- Do not exceed 100 IDs/usernames per call for bulk endpoints.
- Default `max_pages=1` on paginated X v2 endpoints; only paginate further
  when the user explicitly asks for more.
- For graph tools, pass a sensible `limit` (default 10) unless the user
  specifies one.
- Provide concise responses that summarise what the tool returned.
- When the tool result includes a `tweetUrl` column (form
  `https://x.com/i/status/<tweet_id>`), surface it as a clickable link
  alongside each tweet so the user can open the original on X.

Constraints:
- Use only the provided X tools — do not call other APIs or fabricate data.
- The integration is read-only. If the user asks to post, like, follow, or
  retweet, explain that those write actions are not available.
"""

# The SPARQL templates of XSparqlQueries.ttl the in-engine agent loaded (the
# four count queries of that file are the app's, not the agent's).
SPARQL_TOOLS = (
    "find_top_liked_tweets",
    "find_top_retweeted_tweets",
    "find_top_impression_tweets",
    "find_top_engaging_tweets",
    "find_tweets_by_author",
    "find_tweets_by_username",
    "find_tweets_containing_keyword",
    "find_tweets_in_language",
    "find_tweets_since",
    "find_tweet_by_id",
    "find_top_authors_by_tweet_count",
    "find_language_distribution",
    "find_tweets_by_search_query",
    "list_ingested_search_queries",
)

# The agent's searches share one ledger, beside the filters' ones.
AGENT_BUDGET_KEY = "agent"
PACKAGE_DIR = Path(__file__).resolve().parents[1]


def agent_search_limits(configuration: Any) -> BudgetLimits:
    """The caps of the agent's ``x_search_recent_tweets``, from the module
    configuration's ``agent_cost_per_tweet_usd``, ``agent_daily_max_tweets``,
    ``agent_daily_max_usd``, ``agent_monthly_max_tweets`` and
    ``agent_monthly_max_usd`` (as a search filter's; unset: no cap, $0.005 a
    tweet). Every search is recorded either way."""

    def setting(name: str, default: Any = None) -> Any:
        value = getattr(configuration, f"agent_{name}", None)
        return default if value is None else value

    return BudgetLimits(
        cost_per_tweet_usd=float(setting("cost_per_tweet_usd", 0.005)),
        daily_max_tweets=setting("daily_max_tweets"),
        daily_max_usd=setting("daily_max_usd"),
        monthly_max_tweets=setting("monthly_max_tweets"),
        monthly_max_usd=setting("monthly_max_usd"),
    )


def integration_tools(module: Any) -> list[Any]:
    """The X v2 API tools, the search through the agent's ledger; none
    without a bearer token."""
    if not module.bearer_token:
        logger.warning(
            "applications.x: secret %s not set; the agent has no X API tools",
            module.configuration.bearer_token_secret,
        )
        return []
    integration = x_integration_for(module)
    sync = module.sync
    ledger = budget_ledger(
        sync.engine.services.object_storage,
        module.configuration.datastore_path,
        AGENT_BUDGET_KEY,
        agent_search_limits(module.configuration),
    )

    async def search(query: str, **options: Any) -> dict:
        # The ledger reads and writes object storage synchronously: off the loop.
        return await asyncio.to_thread(
            search_with_budget, ledger, sync.run, integration, query, **options
        )

    return as_tools(integration.configuration, search_recent_tweets=search)


async def create_agent(module: Any) -> Agent:
    """The X agent of ``module`` (the SDK ``ABIModule``, after ``sync`` and
    ``bearer_token`` are set)."""
    tools = integration_tools(module) + query_tools(
        module_queries(PACKAGE_DIR),
        module.engine.services.triple_store,
        names=SPARQL_TOOLS,
    )
    return await build_agent(
        module.engine,
        module.module_id,
        name=NAME,
        description=DESCRIPTION,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        chat_model=module.configuration.chat_model,
    )
