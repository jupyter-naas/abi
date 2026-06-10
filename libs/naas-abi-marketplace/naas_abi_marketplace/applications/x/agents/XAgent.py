from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class XAgent(Agent):
    name: str = "X"
    description: str = (
        "Helps you explore X (Twitter) — users, timelines, follows, "
        "and recent tweet search via the v2 API, plus SPARQL questions "
        "over tweets already ingested into the ABI knowledge graph."
    )
    # Wikimedia Commons hosts the canonical 2023 X logo. The Special:FilePath
    # URL is content-addressed and redirects to a stable upload.wikimedia.org
    # CDN URL — using the resolved CDN URL directly avoids the 302 hop.
    logo_url: str = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/"
        "X_logo_2023_original.svg/250px-X_logo_2023_original.svg.png"
    )
    suggestions: list[dict] = [
        {
            "label": "Top liked tweets",
            "value": "Show me the top 10 most liked tweets in the knowledge graph",
            "description": "Rank collected tweets by like count",
        },
        {
            "label": "Most viral tweets",
            "value": "What are the most retweeted tweets?",
            "description": "Rank collected tweets by retweet count",
        },
        {
            "label": "Top engaging tweets",
            "value": "Which tweets drove the most total engagement (likes + retweets + replies + quotes)?",
            "description": "Combined engagement score across all interaction types",
        },
        {
            "label": "Most active authors",
            "value": "Who are the most prolific authors in the knowledge graph?",
            "description": "Rank X users by number of tweets collected",
        },
        {
            "label": "Language breakdown",
            "value": "What is the language distribution of collected tweets?",
            "description": "See which languages dominate the ingested dataset",
        },
        {
            "label": "Search by keyword",
            "value": "Find tweets containing the keyword ",
            "description": "Case-insensitive substring search across tweet text",
        },
        # {
        #     "label": "Active ingestion filters",
        #     "value": "List all ingested search queries and how many tweets each one collected",
        #     "description": "Inspect which X v2 search filters are feeding the knowledge graph",
        # },
    ]
    system_prompt: str = """
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
- Generate a tweet dump *file* (`x_generate_tweet_dump_file`) — calls
  search_recent_tweets, writes the result as an NDJSON file under
  `x/dumps/` in object storage, and returns the file's prefix + key.
  The drop triggers the auto-ingestion sensor, so the same tweets
  become queryable via the graph tools a few seconds after the file
  lands. Use this when the user asks for a dataset / export, or when
  they want the graph back-filled with a deliberate query slice.

Graph SPARQL tools — use them when the user asks about tweets **already
collected** in the ABI knowledge graph (i.e. analytical / aggregate
questions over previously-ingested data):
- `find_top_liked_tweets`, `find_top_retweeted_tweets`,
  `find_top_impression_tweets`, `find_top_engaging_tweets` — engagement
  rankings with a `limit`.
- `find_tweets_by_author` — tweets by a specific `author_id`.
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
- `list_ingested_tweet_files` — every tweet dataset file (uploaded JSON /
  NDJSON dump) ingested into the graph via XFileIngestionPipeline, with
  sha256, file size, record count and import timestamp. Use this when
  the user asks "what tweet datasets / dumps have we loaded?" or
  "show me the files we've ingested".

Routing rules:
- "Most liked / retweeted / viewed / engaging tweets" → graph tool.
- "Top authors / language distribution / tweets containing X / tweets since X" → graph tool.
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
    @classmethod
    def get_tools(cls) -> list:
        """Load the X SPARQL competency-question tools from the templatable
        SPARQL query module. The tools are loaded by name so adding a new
        query to ``XSparqlQueries.ttl`` requires registering its label here
        as well."""
        from naas_abi_core.module.Module import BaseModule
        from naas_abi_core.modules.templatablesparqlquery import (
            ABIModule as TemplatableSparqlQueryABIModule,
        )

        from naas_abi_marketplace.applications.x import ABIModule

        templatable_sparql_query_module: BaseModule = (
            ABIModule.get_instance().engine.modules[
                "naas_abi_core.modules.templatablesparqlquery"
            ]
        )
        assert isinstance(
            templatable_sparql_query_module, TemplatableSparqlQueryABIModule
        ), "TemplatableSparqlQueryABIModule must be a subclass of BaseModule"

        x_sparql_tools = [
            "find_top_liked_tweets",
            "find_top_retweeted_tweets",
            "find_top_impression_tweets",
            "find_top_engaging_tweets",
            "find_tweets_by_author",
            "find_tweets_containing_keyword",
            "find_tweets_in_language",
            "find_tweets_since",
            "find_tweet_by_id",
            "find_top_authors_by_tweet_count",
            "find_language_distribution",
            "find_tweets_by_search_query",
            "list_ingested_search_queries",
            "list_ingested_tweet_files",
        ]
        return list(templatable_sparql_query_module.get_tools(x_sparql_tools))

    @classmethod
    def _get_pipeline_tools(cls, x_integration_config) -> list:
        """Pipeline tools the agent can invoke directly.

        Only includes pipelines that make sense as agent-facing actions
        (vs. ones that only run from orchestration sensors). Today that's
        just the dump-file generator: the user can say "generate a tweet
        dump for X" and the auto-ingestion sensor will then load the
        produced file into the graph asynchronously.
        """
        from naas_abi_marketplace.applications.x import ABIModule
        from naas_abi_marketplace.applications.x.integrations.XIntegration import (
            XIntegration,
        )
        from naas_abi_marketplace.applications.x.pipelines.XGenerateTweetDumpPipeline import (
            XGenerateTweetDumpPipeline,
            XGenerateTweetDumpPipelineConfiguration,
        )

        module = ABIModule.get_instance()
        x_integration = XIntegration(x_integration_config)
        dump_pipeline = XGenerateTweetDumpPipeline(
            XGenerateTweetDumpPipelineConfiguration(
                x_integration=x_integration,
                object_storage=module.engine.services.object_storage,
            )
        )
        return list(dump_pipeline.as_tools())

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "XAgent":
        from naas_abi_core.engine.context import get_default_model_registry
        from naas_abi_marketplace.applications.x import ABIModule
        from naas_abi_marketplace.applications.x.integrations.XIntegration import (
            XIntegrationConfiguration,
        )
        from naas_abi_marketplace.applications.x.integrations.XIntegration import (
            as_tools as XIntegration_tools,
        )

        module = ABIModule.get_instance()
        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()

        x_integration_config = XIntegrationConfiguration(
            bearer_token=module.configuration.bearer_token
        )
        # tools = list(XIntegration_tools(x_integration_config))
        tools = cls.get_tools()
        # tools += cls._get_pipeline_tools(x_integration_config)

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return XAgent(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            tools=tools,
            agents=[],
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
