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
from pydantic import BaseModel, Field, model_validator

# Cadence applied to a search filter that sets neither `interval_seconds` nor
# `cron` — the sensor wakes every minute (the spend guard bounds the spend).
DEFAULT_SEARCH_INTERVAL_SECONDS = 60

# Cadence applied to a files-reprocess entry that sets neither `interval_seconds`
# nor `cron` — the sensor wakes every 1 h 30 min.
DEFAULT_FILES_INTERVAL_SECONDS = 5400

def validate_cron(value: str, setting: str) -> str:
    """Return *value* stripped, or raise if it is not cron-shaped.

    Full expression validation happens in Dagster at definition time; this
    catches the obvious typos while the ABI config is still loading, where the
    error can name the offending *setting*.
    """
    cron = value.strip()
    if not cron or not (cron.startswith("@") or len(cron.split()) in (5, 6)):
        raise ValueError(
            f"{setting}: 'cron' must be a 5- or 6-field cron expression or an "
            f"@-macro (e.g. '0 * * * *', '@hourly'), got {value!r}."
        )
    return cron


class XTweetSearchWorkflowConfiguration(BaseModel):
    """One configured X v2 search filter that the XOrchestration polls on a
    schedule via :class:`XSearchRecentTweetsWorkflow`.

    The workflow recovers each query's ``since_id`` from a small cursor kept in
    object storage and saves each new response as a JSON envelope.
    It does not map anything into the graph — saving an envelope publishes an
    ObjectPut event that the ``search_recent_tweets_event`` sensor consumes to
    map it. Each entry produces its own Dagster job, plus **one** trigger that
    runs it — fetching only tweets newer than the last persisted ``newest_id``
    for the same ``query``:

    * ``interval_seconds`` → a Dagster **sensor** that wakes on that cadence
      (elapsed-time based: "every hour", drifting with the daemon).
    * ``cron`` → a Dagster **schedule** firing at those wall-clock times, in
      UTC (e.g. ``"0 * * * *"`` — top of every hour, ``"0 9 * * 1-5"`` — 09:00
      UTC on weekdays).

    Setting both is a configuration error; setting neither falls back to a
    sensor on ``DEFAULT_SEARCH_INTERVAL_SECONDS``. The trigger starts RUNNING and
    skips a tick while a previous run for the same filter is still in flight.
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
    interval_seconds: int | None = Field(
        default=None,
        ge=30,
        description=(
            "Minimum delay between two sensor evaluations. Mutually exclusive "
            f"with `cron`; when neither is set, defaults to "
            f"{DEFAULT_SEARCH_INTERVAL_SECONDS}s."
        ),
    )
    cron: str | None = Field(
        default=None,
        description=(
            "Cron expression (5 or 6 fields, or a @-macro such as '@hourly') "
            "firing this filter at fixed wall-clock times in UTC, e.g. "
            "'0 * * * *' (top of every hour). Mutually exclusive with "
            "`interval_seconds`."
        ),
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
    save_every_pages: int | None = Field(
        default=10,
        ge=1,
        description=(
            "Workflow writes a new search envelope every N pages during a run "
            "(whichever of save_every_pages / save_every_tweets hits first). "
            "Null disables the pages threshold."
        ),
    )
    save_every_tweets: int | None = Field(
        default=1000,
        ge=1,
        description=(
            "Workflow writes a new search envelope every N tweets during a run "
            "(whichever of save_every_pages / save_every_tweets hits first). "
            "Null disables the tweets threshold."
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
    count_recent_tweets: bool = Field(
        default=False,
        description=(
            "Also follow the recent-post COUNT for this query at the same time "
            "as the tweets. When true, each search run additionally fetches the "
            "newly completed hourly counts (free counts endpoint — no tweet "
            "budget) and maps them into the x_recent_posts_count graph. The "
            "query is also added to the Recent Tweets app dropdown. App snapshot "
            "republish is controlled separately by ``app_publish``."
        ),
    )
    app_publish: bool = Field(
        default=False,
        description=(
            "After fetching, republish ``x/apps/x_proxy/`` JSON snapshots (+ web "
            "export) on this filter's tick. Defaults to false — a publish reads "
            "the whole graph and re-renders every snapshot, which costs far more "
            "than the fetch itself and grows with the graph, while the hourly "
            "``x_build_pipeline_hub`` schedule already rebuilds the app from the same "
            "state. Turn it on only when the dashboard must follow each tick."
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

    @model_validator(mode="after")
    def _resolve_schedule_mode(self) -> "XTweetSearchWorkflowConfiguration":
        """Exactly one trigger per filter: sensor cadence *or* cron schedule.

        Both set is a configuration error (the two would run the same filter
        twice); neither falls back to a sensor on the default cadence.
        """
        if self.cron is not None and self.interval_seconds is not None:
            raise ValueError(
                f"search_recent_tweets_workflow[{self.name!r}]: set either "
                f"'interval_seconds' (sensor cadence) or 'cron' (schedule), "
                f"not both."
            )

        if self.cron is not None:
            self.cron = validate_cron(
                self.cron, f"search_recent_tweets_workflow[{self.name!r}]"
            )
        elif self.interval_seconds is None:
            self.interval_seconds = DEFAULT_SEARCH_INTERVAL_SECONDS

        return self


class XAppConfiguration(BaseModel):
    """Publishing controls for the Nexus Recent Tweets app (``x/apps/x_proxy/``).

    Independent of Dagster trigger default status and of ``count_recent_tweets``
    on search filters. When ``publish`` is true, orchestrations that update the
    graph (event map, files reprocess, count cycle, search tick) call
    :func:`publish_x_app` to refresh JSON snapshots + the static web export.
    """

    publish: bool = Field(
        default=True,
        description=(
            "Republish ``x/apps/x_proxy/`` snapshots (and web export) after ingest / "
            "count cycles that update the graph. Set false to keep fetching and "
            "mapping without refreshing the catalog app."
        ),
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
    graph triples. Set ``app_publish: true`` to also republish the Recent Tweets
    catalog app on every successful map — off by default, since the hourly
    ``x_build_pipeline_hub`` schedule already rebuilds it from the same graph state.
    Independent of this entry's ``enabled`` flag (``enabled`` only controls
    whether the Dagster sensor starts RUNNING).
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
        default=True,
        description=(
            "Deprecated legacy flag (ignored). ObjectPut ingestion sensors start "
            "RUNNING when the entry is listed; stop them from the Dagster UI."
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
            "cursor per sensor evaluation. Further capped by free concurrency "
            "slots (``max_concurrent_runs`` minus in-flight runs for this job)."
        ),
    )
    max_concurrent_runs: int = Field(
        default=1,
        ge=1,
        description=(
            "Max Dagster runs of this job allowed queued/running at once. The "
            "sensor checks this *before* ``query_for_consumer`` so the durable "
            "event cursor does not advance when every slot is already taken."
        ),
    )
    persist: bool = Field(
        default=True,
        description="Persist the mapped tweet triples to the triple store.",
    )
    app_publish: bool = Field(
        default=False,
        description=(
            "After mapping an envelope into the graph, republish ``x/apps/x_proxy/`` "
            "JSON snapshots (+ web export). Defaults to false — the hourly "
            "``x_build_pipeline_hub`` schedule already rebuilds the app from the graph, "
            "so turn this on only when the dashboard must follow each envelope. "
            "Independent of ``enabled``."
        ),
    )


class XSearchRecentTweetsFilesConfiguration(BaseModel):
    """One configured files-reprocessing trigger built by
    :class:`XSearchRecentTweetsFilesOrchestration`.

    Each entry produces its own (job, trigger) pair — a **sensor** when the
    entry sets ``interval_seconds`` (elapsed-time cadence) or a **schedule**
    when it sets ``cron`` (wall-clock times, UTC). Unless a previous run is
    still in flight, the trigger starts a job that sweeps every persisted search
    envelope under ``prefix`` and feeds it to
    :class:`XSearchRecentTweetsPipeline` in ``file_path`` mode. When
    ``skip_existing`` is true the job first reads the ``x:file_path`` of every
    ``x:SearchResultSet`` already mapped and reprocesses only the envelopes not
    yet in the graph.

    Unlike ``search_recent_tweets_event`` (event-driven, one envelope per
    ObjectPut), this sweeps the whole folder on a fixed cadence — use it to
    backfill / re-ingest after a mapping change without re-querying the X API.
    Optional ``max_age_hours`` limits the sweep to envelopes whose filename
    timestamp falls within the last N hours.
    """

    name: str = Field(
        description=(
            "Short identifier (letters/digits/underscores) used to name the "
            "generated Dagster job and sensor — must be unique across the "
            "module's search_recent_tweets_files entries."
        )
    )
    enabled: bool = Field(
        default=True,
        description=(
            "Deprecated legacy flag (ignored). Reprocess triggers start RUNNING "
            "when the entry is listed; stop them from the Dagster UI."
        ),
    )
    interval_seconds: int | None = Field(
        default=None,
        ge=60,
        description=(
            "Minimum delay between two sensor evaluations. Mutually exclusive "
            f"with `cron`; when neither is set, defaults to "
            f"{DEFAULT_FILES_INTERVAL_SECONDS}s."
        ),
    )
    cron: str | None = Field(
        default=None,
        description=(
            "Cron expression (5 or 6 fields, or a @-macro such as '@hourly') "
            "firing this sweep at fixed wall-clock times in UTC. Mutually "
            "exclusive with `interval_seconds`."
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
    max_age_hours: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Only reprocess envelopes whose filename timestamp is within the "
            "last N hours (parsed from ``<iso-ts>_<slug>.json``). ``null`` "
            "(default) means no age filter — sweep every file under prefix."
        ),
    )
    persist: bool = Field(
        default=True,
        description="Persist the mapped tweet triples to the triple store.",
    )
    app_publish: bool = Field(
        default=False,
        description=(
            "After reprocessing at least one envelope into the graph, republish "
            "``x/apps/x_proxy/`` JSON snapshots (+ web export). Defaults to false — "
            "the hourly ``x_build_pipeline_hub`` schedule already rebuilds the app from "
            "the graph. Independent of ``enabled``."
        ),
    )

    @model_validator(mode="after")
    def _resolve_schedule_mode(self) -> "XSearchRecentTweetsFilesConfiguration":
        """Exactly one trigger per entry: sensor cadence *or* cron schedule."""
        if self.cron is not None and self.interval_seconds is not None:
            raise ValueError(
                f"search_recent_tweets_files[{self.name!r}]: set either "
                f"'interval_seconds' (sensor cadence) or 'cron' (schedule), "
                f"not both."
            )

        if self.cron is not None:
            self.cron = validate_cron(
                self.cron, f"search_recent_tweets_files[{self.name!r}]"
            )
        elif self.interval_seconds is None:
            self.interval_seconds = DEFAULT_FILES_INTERVAL_SECONDS

        return self


class XCountFollowConfiguration(BaseModel):
    """One configured X query whose recent-post counts appear in the dashboard.

    Counts are fetched and mapped when a search filter opts in via
    ``count_recent_tweets: true`` on the same ``query``, or when an event/files
    orchestration maps a search envelope whose query is listed here. The
    ``enabled`` flag controls whether this entry is included in the dashboard
    catalog (``x/apps/x_proxy/``).
    """

    name: str = Field(
        description=(
            "Short identifier (letters/digits/underscores), unique across the "
            "module's count_recent_tweets_workflow entries. Used as the object-"
            "storage slug and the dashboard option key."
        )
    )
    query: str = Field(
        description=(
            "X v2 search query (1-4096 chars) whose recent-post count to follow. "
            "See https://developer.twitter.com/en/docs/twitter-api/tweets/search/integrate/build-a-query"
        )
    )
    label: str | None = Field(
        default=None,
        description="Human-readable label shown in the dashboard query dropdown.",
    )
    enabled: bool = Field(
        default=False,
        description=(
            "Include this query in the dashboard catalog. Counts still require "
            "a search filter with ``count_recent_tweets: true`` or manual ingest."
        ),
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
            # One trigger per entry, running XSearchRecentTweetsWorkflow for
            # `query` (incrementally, from the last seen tweet id) to fetch and
            # SAVE the JSON envelopes. Graph mapping is NOT done here — each
            # saved envelope's ObjectPut event drives the
            # search_recent_tweets_event sensor below.
            #
            # Pick ONE cadence per entry — setting both is a config error:
            #   interval_seconds: 3600   -> sensor, every hour of elapsed time
            #   cron: "0 * * * *"        -> schedule, at :00 wall-clock (UTC)
            # Omit both and the entry falls back to a 60s sensor. Triggers start
            # RUNNING and skip a tick while the previous run for that filter is
            # still in flight.
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
              # (a) interval-driven — a Dagster SENSOR wakes every
              #     `interval_seconds` of elapsed time.
              - name: ai_llms
                query: "(openai OR anthropic OR \"llm\" OR \"large language model\") lang:en -is:retweet"
                interval_seconds: 3600   # hourly; the spend guard stops it early
                max_results: 100
                max_pages: 1
                sort_order: recency      # 'recency' or 'relevancy'
                save_every_pages: 10     # flush envelope every N pages
                save_every_tweets: 1000  # …or every N tweets (whichever first)
                persist: true
                app_publish: false       # opt in to republish x/apps/x_proxy/ per tick
                cost_per_tweet_usd: 0.005
                daily_max_usd: 20        # ~4000 tweets/day at $0.005
                monthly_max_usd: 250     # ~50000 tweets/month at $0.005
                # daily_max_tweets / monthly_max_tweets are also accepted if you
                # prefer to cap by count instead of (or alongside) USD.

              # (b) cron-driven — a Dagster SCHEDULE fires at fixed wall-clock
              #     times (UTC). Same options as above, `cron` replacing
              #     `interval_seconds`; setting BOTH raises at config load.
              - name: drones_business_hours
                query: "(drone OR uas OR uav) lang:en -is:retweet"
                cron: "*/15 9-17 * * 1-5"  # every 15 min, 09:00-17:59 UTC, Mon-Fri
                max_results: 100
                max_pages: 1
                sort_order: recency
                persist: true
                cost_per_tweet_usd: 0.005
                daily_max_usd: 5
                monthly_max_usd: 100

            # ----- Event-driven mapping sensors ----------------------------
            # One (job, sensor) pair per entry. Each sensor subscribes to
            # ObjectPut events on the bus and, for every new envelope written
            # under `prefix` (by the search_recent_tweets_workflow jobs), maps
            # the file into the graph via XSearchRecentTweetsPipeline — no
            # polling of object storage; each put is processed exactly once via
            # a durable consumer cursor keyed on the sensor's `name`. Sensors
            # start RUNNING. This is the mapping half of the flow: the workflow
            # saves envelopes, this sensor turns them into triples.
            search_recent_tweets_event:
              - name: search_envelopes
                enabled: true
                interval_seconds: 30     # minimum delay between evaluations
                prefix: x/search_recent_tweets
                events_per_tick: 100     # max ObjectPut events drained per tick
                max_concurrent_runs: 1   # skip (no cursor advance) when full
                persist: true
                app_publish: false       # opt in to republish x/apps/x_proxy/ per map

            # ----- Scheduled files-reprocessing triggers -------------------
            # One (job, trigger) pair per entry — sensor (`interval_seconds`)
            # or schedule (`cron`), not both. Unless a previous run is still in
            # flight, the trigger sweeps every search envelope under `prefix`
            # and feeds it to XSearchRecentTweetsPipeline. With
            # `skip_existing: true` the run first reads the x:file_path of
            # every x:SearchResultSet already in the graph and reprocesses
            # only the envelopes not yet mapped. Triggers start RUNNING. Use it
            # to backfill / re-ingest a folder on a cadence without re-querying
            # the X API.
            search_recent_tweets_files:
              - name: reprocess_envelopes
                enabled: true
                cron: "0,15,30,45 * * * *"  # 5 min after :10/:25/:40/:55 search ticks
                prefix: x/search_recent_tweets
                skip_existing: true      # skip files already in the graph
                max_age_hours: 24        # only envelopes from the last 24h
                persist: true
                app_publish: false       # opt in to republish x/apps/x_proxy/ after sweep

            # ----- Post-count dashboard catalog ------------------------------
            # Queries listed here appear in the "Post Count Following" dashboard
            # when `enabled: true`. Fetch counts via `count_recent_tweets: true`
            # on a matching search_recent_tweets_workflow filter.
            count_recent_tweets_workflow:
              - name: drones
                query: "(drone OR drones OR uas OR uav) lang:en -is:retweet"
                label: "Drones / UAS"
                enabled: true
        """

        bearer_token: str | None = None
        datastore_path: str = "x"
        ontology_namespace: str = "http://ontology.naas.ai/x/"
        graph_name: str = "http://ontology.naas.ai/graph/x"
        search_recent_tweets_workflow: list[XTweetSearchWorkflowConfiguration] = []
        search_recent_tweets_event: list[XSearchRecentTweetsEventConfiguration] = []
        search_recent_tweets_files: list[XSearchRecentTweetsFilesConfiguration] = []
        # ----- Post-count dashboard catalog ----------------------------------
        # One entry per query shown in the "Post Count Following" dashboard.
        #
        #     count_recent_tweets_workflow:
        #       - name: drones
        #         query: "(drone OR drones OR uas OR uav) lang:en -is:retweet"
        #         label: "Drones / UAS"
        #         enabled: true
        count_recent_tweets_workflow: list[XCountFollowConfiguration] = []
        # ----- Recent Tweets catalog app (x/apps/x_proxy/) ------------------------
        # Snapshot republish is independent of Dagster trigger default status and of
        # ``count_recent_tweets`` on search filters.
        #
        #     app:
        #       publish: true
        app: XAppConfiguration = Field(default_factory=XAppConfiguration)

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
        # Serve the X dashboard + its whole JSON dataset from object storage
        # (x/apps/x_proxy/) via /app-html/x/apps/x_proxy/… — registered before the Nexus
        # static catch-all so the published dashboard wins.
        try:
            from naas_abi_marketplace.applications.x.apps.x_proxy.routes import (
                register_x_count_app_routes,
            )

            # Object storage only: the app reads a published dataset, so no
            # SPARQL runs at request time and the API needs no triple store.
            register_x_count_app_routes(app, self.engine.services.object_storage)
        except Exception as exc:  # noqa: BLE001
            from naas_abi_core import logger

            logger.warning(f"XModule: failed to register X count app routes ({exc})")

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
