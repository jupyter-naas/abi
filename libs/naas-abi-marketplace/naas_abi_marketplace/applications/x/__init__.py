from fastapi import FastAPI
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import (
    TripleStoreService,
)
from pydantic import BaseModel, Field


class XTweetSearchWorkflowConfiguration(BaseModel):
    """One configured X v2 search filter that the XOrchestration polls on a
    schedule via :class:`XSearchRecentTweetsWorkflow`.

    The workflow recovers each query's ``since_id`` from the persisted JSON
    envelopes in object storage and saves each new response as a JSON envelope.
    It does not map anything into the graph — saving an envelope publishes an
    ObjectPut event that the ``search_recent_tweets_event`` sensor consumes to
    map it. Each entry produces its own Dagster job + sensor pair; the sensor
    wakes every ``interval_seconds`` and triggers a run that fetches only tweets
    newer than the last persisted ``newest_id`` for the same ``query``.
    """

    name: str = Field(
        description=(
            "Short identifier (letters/digits/underscores) used to name "
            "the generated Dagster job and sensor — must be unique across "
            "the module's tweet_search_workflow_pipelines."
        )
    )
    query: str = Field(
        description=(
            "X v2 search query (1-4096 chars). See "
            "https://developer.twitter.com/en/docs/twitter-api/tweets/search/integrate/build-a-query"
        )
    )
    interval_seconds: int = Field(
        default=60,
        ge=30,
        description="Minimum delay between two sensor evaluations.",
    )
    max_results: int = Field(
        default=100,
        ge=10,
        le=100,
        description="Page size forwarded to X v2 search_recent_tweets.",
    )
    max_pages: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Maximum pages to fetch per run. Set null to exhaust every new "
            "tweet since the last run; combined with the since_id cursor this "
            "caps the amount of work done per tick."
        ),
    )
    sort_order: str = Field(
        default="recency",
        description="Order results are returned in: 'recency' or 'relevancy'.",
    )
    persist: bool = Field(
        default=True,
        description=(
            "Whether the workflow inserts the mapped tweet graph into the "
            "configured triple store. Set false to fetch and persist the JSON "
            "envelopes (and write the .ttl) without writing to the triple store."
        ),
    )

    # ----- Spend guard (per filter) --------------------------------------
    # XSearchRecentTweetsWorkflow bills `cost_per_tweet_usd` per tweet
    # ('resource') returned by search_recent_tweets. A persistent usage ledger
    # in object storage (keyed by this filter's `name`) tracks how many tweets
    # this filter has retrieved today and this calendar month; once *either*
    # the daily or the monthly cap is reached the workflow returns zero results
    # WITHOUT calling the X API, so the sensor can keep ticking (e.g. hourly)
    # without spending past the budget. Caps may be given as a tweet count or a
    # USD amount (converted via `cost_per_tweet_usd`); if both are set for the
    # same period the more restrictive one wins. Leave a cap null to disable it.
    cost_per_tweet_usd: float = Field(
        default=0.005,
        gt=0,
        description="USD billed per tweet returned by search_recent_tweets.",
    )
    daily_max_tweets: int | None = Field(
        default=None,
        ge=0,
        description="Max tweets this filter may retrieve per UTC day (null = no limit).",
    )
    daily_max_usd: float | None = Field(
        default=None,
        ge=0,
        description="Max USD this filter may spend per UTC day (null = no limit).",
    )
    monthly_max_tweets: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Max tweets this filter may retrieve per calendar month (null = no limit)."
        ),
    )
    monthly_max_usd: float | None = Field(
        default=None,
        ge=0,
        description="Max USD this filter may spend per calendar month (null = no limit).",
    )


class XSearchRecentTweetsEventConfiguration(BaseModel):
    """One configured event-driven ingestion sensor built by
    :class:`XSearchRecentTweetsEventOrchestration`.

    Each entry produces its own (job, sensor) pair: the sensor subscribes to
    ``ObjectPut`` events on the bus and, for every new envelope written under
    ``prefix``, maps the file into the graph via ``XSearchRecentTweetsPipeline``
    — no polling of object storage; each put is processed exactly once via a
    durable consumer cursor keyed on the sensor.

    This is the mapping half of the search flow: ``search_recent_tweets_workflow``
    only fetches and saves envelopes; this sensor turns each saved envelope into
    graph triples.
    """

    name: str = Field(
        description=(
            "Short identifier (letters/digits/underscores) used to name the "
            "generated Dagster job and sensor and to key the durable event "
            "consumer — must be unique across the module's "
            "search_recent_tweets_event entries."
        )
    )
    enabled: bool = Field(
        default=False,
        description=(
            "Start the ObjectPut ingestion sensor RUNNING. Defaults to false "
            "(the sensor is created STOPPED; enable it from the Dagster UI)."
        ),
    )
    interval_seconds: int = Field(
        default=30,
        ge=30,
        description="Minimum delay between two sensor evaluations.",
    )
    prefix: str = Field(
        default="x/search_recent_tweets",
        description=(
            "Object-storage prefix watched for new tweet envelopes. Must match "
            "where the search workflow / integration persist their JSON "
            "envelopes (ObjectStorageService strips the leading 'storage/')."
        ),
    )
    events_per_tick: int = Field(
        default=100,
        ge=1,
        description=(
            "Max undelivered ObjectPut events drained from the durable consumer "
            "cursor per sensor evaluation."
        ),
    )
    persist: bool = Field(
        default=True,
        description="Persist the mapped tweet triples to the triple store.",
    )


class XSearchRecentTweetsFilesConfiguration(BaseModel):
    """One configured files-reprocessing sensor built by
    :class:`XSearchRecentTweetsFilesOrchestration`.

    Each entry produces its own (job, sensor) pair. Every ``interval_seconds``
    the sensor — unless a previous run is still in flight — triggers a job that
    sweeps every persisted search envelope under ``prefix`` and feeds it to
    :class:`XSearchRecentTweetsPipeline` in ``file_path`` mode. When
    ``skip_existing`` is true the job first reads the ``x:file_path`` of every
    ``x:SearchResultSet`` already mapped and reprocesses only the envelopes not
    yet in the graph.

    Unlike ``search_recent_tweets_event`` (event-driven, one envelope per
    ObjectPut), this sweeps the whole folder on a fixed cadence — use it to
    backfill / re-ingest after a mapping change without re-querying the X API.
    """

    name: str = Field(
        description=(
            "Short identifier (letters/digits/underscores) used to name the "
            "generated Dagster job and sensor — must be unique across the "
            "module's search_recent_tweets_files entries."
        )
    )
    enabled: bool = Field(
        default=False,
        description=(
            "Start the reprocess sensor RUNNING. Defaults to false (the sensor "
            "is created STOPPED; enable it from the Dagster UI)."
        ),
    )
    interval_seconds: int = Field(
        default=5400,
        ge=60,
        description=(
            "Minimum delay between two sensor evaluations. Defaults to 5400 "
            "(every 1 h 30 min)."
        ),
    )
    prefix: str = Field(
        default="x/search_recent_tweets",
        description=(
            "Object-storage folder swept (recursively) for search envelopes to "
            "reprocess. Must match where the search workflow / integration "
            "persist their JSON envelopes."
        ),
    )
    skip_existing: bool = Field(
        default=True,
        description=(
            "Reprocess only envelopes whose path is not already the x:file_path "
            "of a mapped x:SearchResultSet. Set false to force a full re-run "
            "over every file (the pipeline's label dedupe still no-ops re-runs)."
        ),
    )
    persist: bool = Field(
        default=True,
        description="Persist the mapped tweet triples to the triple store.",
    )


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_core.modules.templatablesparqlquery",
        ],
        services=[ObjectStorageService, Secret, TripleStoreService, EventService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.x
        enabled: true
        config:
            bearer_token: "{{ secret.X_BEARER_TOKEN }}"

            # ----- Search-workflow pipelines -------------------------------
            # One sensor per entry. Every `interval_seconds` the sensor runs
            # XSearchRecentTweetsWorkflow for `query` (incrementally, from the
            # last seen tweet id) to fetch and SAVE the JSON envelopes. Graph
            # mapping is NOT done here — each saved envelope's ObjectPut event
            # drives the search_recent_tweets_event sensor below.
            #
            # Spend guard (per filter): search_recent_tweets bills
            # `cost_per_tweet_usd` per tweet ('resource') returned. A usage
            # ledger keyed by this filter's `name` tracks tweets retrieved today
            # and this calendar month; once EITHER the daily or monthly cap is
            # reached the run fetches nothing (no X API call) until the next
            # day / month — so the sensor can keep ticking (e.g. hourly) without
            # spending past the budget. Caps may be a tweet count or a USD
            # amount; if both are set on a period the stricter one wins. The
            # example below caps this filter at $20/day and $250/month.
            search_recent_tweets_workflow:
              - name: ai_llms
                query: "(openai OR anthropic OR \"llm\" OR \"large language model\") lang:en -is:retweet"
                interval_seconds: 3600   # hourly; the spend guard stops it early
                max_results: 100
                max_pages: 1
                sort_order: recency      # 'recency' or 'relevancy'
                persist: true
                cost_per_tweet_usd: 0.005
                daily_max_usd: 20        # ~4000 tweets/day at $0.005
                monthly_max_usd: 250     # ~50000 tweets/month at $0.005
                # daily_max_tweets / monthly_max_tweets are also accepted if you
                # prefer to cap by count instead of (or alongside) USD.

            # ----- Event-driven mapping sensors ----------------------------
            # One (job, sensor) pair per entry. Each sensor subscribes to
            # ObjectPut events on the bus and, for every new envelope written
            # under `prefix` (by the search_recent_tweets_workflow jobs), maps
            # the file into the graph via XSearchRecentTweetsPipeline — no
            # polling of object storage; each put is processed exactly once via
            # a durable consumer cursor keyed on the sensor's `name`. Created
            # STOPPED unless `enabled: true`. This is the mapping half of the
            # flow: the workflow saves envelopes, this sensor turns them into
            # triples.
            search_recent_tweets_event:
              - name: search_envelopes
                enabled: true
                interval_seconds: 30     # minimum delay between evaluations
                prefix: x/search_recent_tweets
                events_per_tick: 100     # max ObjectPut events drained per tick
                persist: true

            # ----- Scheduled files-reprocessing sensors --------------------
            # One (job, sensor) pair per entry. Every `interval_seconds` the
            # sensor — unless a previous run is still in flight — sweeps every
            # search envelope under `prefix` and feeds it to
            # XSearchRecentTweetsPipeline. With `skip_existing: true` the run
            # first reads the x:file_path of every x:SearchResultSet already in
            # the graph and reprocesses only the envelopes not yet mapped.
            # Created STOPPED unless `enabled: true`. Use it to backfill /
            # re-ingest a folder on a cadence without re-querying the X API.
            search_recent_tweets_files:
              - name: reprocess_envelopes
                enabled: true
                interval_seconds: 5400   # every 1 h 30 min
                prefix: x/search_recent_tweets
                skip_existing: true      # skip files already in the graph
                persist: true
        """

        bearer_token: str | None = None
        datastore_path: str = "x"
        ontology_namespace: str = "http://ontology.naas.ai/x/"
        graph_name: str = "http://ontology.naas.ai/graph/x"
        search_recent_tweets_workflow: list[XTweetSearchWorkflowConfiguration] = []
        search_recent_tweets_event: list[XSearchRecentTweetsEventConfiguration] = []
        search_recent_tweets_files: list[XSearchRecentTweetsFilesConfiguration] = []

    # on_initialized is called by the engine after all modules and services have been fully loaded.
    # At this point, you can safely access other modules and services through the engine's interfaces.
    # Override this method to implement any post-initialization logic your module requires.
    def on_initialized(self):
        super().on_initialized()

    # The on_load method is invoked during initial module loading by the engine.
    # At this point, avoid accessing services or other modules, as they have not been loaded yet.
    # Place any logic here that must occur right as the module is loaded, before initialization.
    # You can see it as the constructor of the module.
    def on_load(self):
        super().on_load()

    # Optional FastAPI integration hook.
    # This mirrors how `naas_abi` wires API settings and services into app.state.
    # Override and adapt to your module if you expose HTTP routes.
    def api(self, app: FastAPI) -> None:
        # Example: expose services to your API layer.
        # app.state.object_storage = self.engine.services.object_storage
        # app.state.secret_service = self.engine.services.secret
        # app.state.triple_store = self.engine.services.triple_store
        # app.state.vector_store = self.engine.services.vector_store
        # app.state.bus_service = self.engine.services.bus
        # app.state.key_value_service = self.engine.services.kv

        # Example: mount your FastAPI routes/app factory.
        # from your_module.apps.api.app.main import create_app
        # create_app(app)
        pass
