"""The X module's configuration.

``XConfiguration`` is the module's ``ModuleConfiguration``; its list entries are
the pydantic models below, unchanged from the in-engine module, so an engine
``config.yaml`` ``modules:`` entry of ``naas_abi_marketplace.applications.x``
copied into ``X_CONFIG_FILE`` loads as it is (``common.runtime``), except for
``bearer_token``: the token is the engine secret ``applications.x/X_BEARER_TOKEN``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from naas_abi_sdk import ModuleConfiguration
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)

# Cadence applied to a search filter that sets neither `interval_seconds` nor
# `cron`: its trigger fires every minute (the spend guard bounds the spend).
DEFAULT_SEARCH_INTERVAL_SECONDS = 60

# Cadence applied to a files-reprocess entry that sets neither `interval_seconds`
# nor `cron`: its trigger fires every 1 h 30 min.
DEFAULT_FILES_INTERVAL_SECONDS = 5400


def validate_cron(value: str, setting: str) -> str:
    """Return *value* stripped, or raise if it is not cron-shaped.

    This catches the obvious typos while the configuration loads, where the
    error can name the offending *setting*. ``flows/triggers.py`` then converts
    the expression to the 6-field form NATS schedules take; one NATS refuses is
    logged and its entry left out.
    """
    cron = value.strip()
    if not cron or not (cron.startswith("@") or len(cron.split()) in (5, 6)):
        raise ValueError(
            f"{setting}: 'cron' must be a 5- or 6-field cron expression or an "
            f"@-macro (e.g. '0 * * * *', '@hourly'), got {value!r}."
        )
    return cron


class XTweetSearchWorkflowConfiguration(BaseModel):
    """One configured X v2 search filter, polled by the ``search_recent_tweets``
    workflow through :class:`XSearchRecentTweetsWorkflow`.

    The workflow recovers each query's ``since_id`` from a small cursor kept in
    object storage and saves each new response as a JSON envelope; the run then
    maps the envelopes it saved (``map_tweet_envelope`` child runs), follows the
    counts (``count_recent_tweets``), syncs the dataset and, with
    ``app_publish``, republishes the app. Each entry is **one** trigger of the
    workflow, whose ticks carry ``{"filter": <name>}`` and fetch only tweets
    newer than the last persisted ``newest_id`` for the same ``query``:

    * ``interval_seconds`` → an ``Every`` trigger on that cadence.
    * ``cron`` → a ``Cron`` trigger firing at those wall-clock times, in UTC
      (e.g. ``"0 * * * *"``: top of every hour, ``"0 9 * * 1-5"``: 09:00 UTC on
      weekdays).

    Setting both is a configuration error; setting neither falls back to an
    interval of ``DEFAULT_SEARCH_INTERVAL_SECONDS``. A tick whose previous run of
    the same filter is still in flight is SKIPPED (``skip_if_running``).
    """

    name: str = Field(
        description=(
            "Short identifier (letters/digits/underscores): the filter's "
            'trigger input ({"filter": name}) and spend-ledger key, unique '
            "across the module's search_recent_tweets_workflow entries."
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
            "Delay between two ticks of this filter. Mutually exclusive "
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
    # WITHOUT calling the X API, so the trigger can keep ticking (e.g. hourly)
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
    def _resolve_schedule_mode(self) -> XTweetSearchWorkflowConfiguration:
        """Exactly one trigger per filter: an interval *or* a cron.

        Both set is a configuration error (the two would run the same filter
        twice); neither falls back to the default interval.
        """
        if self.cron is not None and self.interval_seconds is not None:
            raise ValueError(
                f"search_recent_tweets_workflow[{self.name!r}]: set either "
                f"'interval_seconds' (a cadence) or 'cron' (wall-clock times), "
                f"not both."
            )

        if self.cron is not None:
            self.cron = validate_cron(
                self.cron, f"search_recent_tweets_workflow[{self.name!r}]"
            )
        elif self.interval_seconds is None:
            self.interval_seconds = DEFAULT_SEARCH_INTERVAL_SECONDS

        return self


class XDatasetConfiguration(BaseModel):
    """Dataset Service read model for X Proxy (incremental sync + dynamic APIs)."""

    sync_enabled: bool = Field(
        default=False,
        description=(
            "Project new search envelopes into namespace ``x`` datasets on "
            "ObjectPut event ingestion and on Files reprocess sweeps (not on "
            "search fetch-only jobs). Requires Dataset Service on the engine."
        ),
    )
    read_enabled: bool = Field(
        default=False,
        description=(
            "Serve paginated user/tweet APIs from Dataset Service and publish "
            "dashboard snapshots (globals, count/search charts) from DuckLake. "
            "Required for ``publish_x_app`` / ``x_build_app_x_proxy``."
        ),
    )
    skip_report_warmup: bool = Field(
        default=False,
        description=(
            "Skip ``ReportXProxyWarmup`` shard rebuild when dataset read path is active."
        ),
    )
    media_max_bytes: int = Field(
        default=250 * 1024 * 1024,
        ge=1024 * 1024,
        description="Maximum bytes per streamed media download.",
    )
    media_batch_size: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Pending media rows processed per media-worker tick.",
    )


class XAppConfiguration(BaseModel):
    """Publishing controls for the Nexus Recent Tweets app (``x/apps/x_proxy/``).

    Independent of ``count_recent_tweets`` on search filters. When ``publish``
    is true, the hourly ``build_app`` job calls :func:`publish_x_app` to refresh
    the JSON snapshots + the static web export (a search filter's or a sweep's
    ``app_publish`` republishes on its own tick, whatever this says).
    """

    publish: bool = Field(
        default=True,
        description=(
            "Republish ``x/apps/x_proxy/`` snapshots (and web export) after ingest / "
            "count cycles that update the graph. Set false to keep fetching and "
            "mapping without refreshing the catalog app."
        ),
    )
    dataset: XDatasetConfiguration = Field(default_factory=XDatasetConfiguration)


class XSearchRecentTweetsEventConfiguration(BaseModel):
    """An event-driven mapping entry of the in-engine module: **not used** here.

    In-engine, each entry mapped the envelopes saved under ``prefix`` as their
    ``ObjectPut`` events arrived. The remote module's mapping is not
    event-driven: each ``search_recent_tweets`` run maps the envelopes it saved,
    and ``search_recent_tweets_files`` entries schedule
    ``reprocess_tweet_envelopes`` for the others. The model is kept so an
    in-engine configuration loads; ``XConfiguration`` warns about the entries.
    """

    name: str = Field(
        description=(
            "Not used by the remote module (kept so an in-engine configuration loads)."
        )
    )
    enabled: bool = Field(
        default=True,
        description=("Not used by the remote module."),
    )
    interval_seconds: int = Field(
        default=30,
        ge=30,
        description="Not used by the remote module.",
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
        description=("Not used by the remote module."),
    )
    max_concurrent_runs: int = Field(
        default=1,
        ge=1,
        description=("Not used by the remote module."),
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
    """One scheduled sweep: a trigger of the ``reprocess_tweet_envelopes`` workflow.

    An ``Every`` trigger when the entry sets ``interval_seconds``, a ``Cron``
    trigger (wall-clock times, UTC) when it sets ``cron``. Each tick carries
    ``prefix``, ``persist``, ``max_age_hours``, ``app_publish`` and ``force``
    (``not skip_existing``); a tick whose previous sweep with the same input is
    still in flight is SKIPPED (``skip_if_running``). The run sweeps the search
    envelopes under ``prefix``, leaves out those already in the graph and the
    dataset (unless ``force``), maps the rest as ``map_tweet_envelope`` child
    runs (``XSearchRecentTweetsPipeline`` in ``file_path`` mode), syncs the
    dataset and, with ``app_publish``, republishes the app.

    Use it to map the envelopes saved by other callers (the agent's tools), and
    to backfill / re-ingest after a mapping change without re-querying the X
    API. Optional ``max_age_hours`` limits the sweep to envelopes whose filename
    timestamp falls within the last N hours.
    """

    name: str = Field(
        description=(
            "Short identifier (letters/digits/underscores), unique across the "
            "module's search_recent_tweets_files entries."
        )
    )
    enabled: bool = Field(
        default=True,
        description=("Deprecated legacy flag (ignored): a listed entry is scheduled."),
    )
    interval_seconds: int | None = Field(
        default=None,
        ge=60,
        description=(
            "Delay between two sweeps. Mutually exclusive "
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
    def _resolve_schedule_mode(self) -> XSearchRecentTweetsFilesConfiguration:
        """Exactly one trigger per entry: an interval *or* a cron."""
        if self.cron is not None and self.interval_seconds is not None:
            raise ValueError(
                f"search_recent_tweets_files[{self.name!r}]: set either "
                f"'interval_seconds' (a cadence) or 'cron' (wall-clock times), "
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
    ``count_recent_tweets: true`` on the same ``query``. The ``enabled`` flag
    controls whether this entry is included in the dashboard catalog
    (``x/apps/x_proxy/``).
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


def _entries(model: type[BaseModel], values: Any, setting: str) -> list[Any]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise TypeError(f"{setting} must be a list, not {type(values).__name__}")
    return [v if isinstance(v, model) else model.model_validate(v) for v in values]


def _unique(entries: list[Any], setting: str) -> None:
    names = [entry.name for entry in entries]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"{setting}: duplicate entry names {duplicates}")


@dataclass
class XConfiguration(ModuleConfiguration):
    """Settings of ``applications.x``, from ``X_<FIELD>`` variables or
    ``X_CONFIG_FILE`` (``common.runtime.configuration_from``)."""

    # Name of the engine secret holding the X API bearer token, under the
    # module's id (``applications.x/X_BEARER_TOKEN``).
    bearer_token_secret: str = "X_BEARER_TOKEN"
    datastore_path: str = "x"
    ontology_namespace: str = "http://ontology.naas.ai/x/"
    graph_name: str = "http://ontology.naas.ai/graph/x"
    # Canonical id of a chat model the engine registers; empty: its default.
    chat_model: str = ""
    # Spend caps of the agent's x_search_recent_tweets tool (ledger key
    # ``agent``), as for a search filter; a cap left None is no cap.
    agent_cost_per_tweet_usd: float = 0.005
    agent_daily_max_tweets: int | None = None
    agent_daily_max_usd: float | None = None
    agent_monthly_max_tweets: int | None = None
    agent_monthly_max_usd: float | None = None
    search_recent_tweets_workflow: list[XTweetSearchWorkflowConfiguration] = field(
        default_factory=list
    )
    # Not used: mapping is not event-driven (the search run maps what it saved).
    # Accepted so an in-engine configuration loads; a warning names it.
    search_recent_tweets_event: list[XSearchRecentTweetsEventConfiguration] = field(
        default_factory=list
    )
    search_recent_tweets_files: list[XSearchRecentTweetsFilesConfiguration] = field(
        default_factory=list
    )
    count_recent_tweets_workflow: list[XCountFollowConfiguration] = field(
        default_factory=list
    )
    app: XAppConfiguration = field(default_factory=XAppConfiguration)
    # Refused when set: the token is an engine secret (``bearer_token_secret``).
    bearer_token: str | None = None

    def __post_init__(self) -> None:
        # From X_<FIELD> variables these are strings.
        self.agent_cost_per_tweet_usd = float(self.agent_cost_per_tweet_usd)
        for name, kind in (
            ("agent_daily_max_tweets", int),
            ("agent_daily_max_usd", float),
            ("agent_monthly_max_tweets", int),
            ("agent_monthly_max_usd", float),
        ):
            value = getattr(self, name)
            if value is not None and value != "":
                setattr(self, name, kind(value))
            else:
                setattr(self, name, None)
        if self.bearer_token:
            raise ValueError(
                "bearer_token is an engine secret for the remote X module: store it "
                f"as applications.x/{self.bearer_token_secret} and remove "
                "bearer_token from the configuration"
            )
        self.search_recent_tweets_workflow = _entries(
            XTweetSearchWorkflowConfiguration,
            self.search_recent_tweets_workflow,
            "search_recent_tweets_workflow",
        )
        self.search_recent_tweets_event = _entries(
            XSearchRecentTweetsEventConfiguration,
            self.search_recent_tweets_event,
            "search_recent_tweets_event",
        )
        self.search_recent_tweets_files = _entries(
            XSearchRecentTweetsFilesConfiguration,
            self.search_recent_tweets_files,
            "search_recent_tweets_files",
        )
        self.count_recent_tweets_workflow = _entries(
            XCountFollowConfiguration,
            self.count_recent_tweets_workflow,
            "count_recent_tweets_workflow",
        )
        for setting in (
            "search_recent_tweets_workflow",
            "search_recent_tweets_files",
            "count_recent_tweets_workflow",
        ):
            _unique(getattr(self, setting), setting)
        if not isinstance(self.app, XAppConfiguration):
            self.app = XAppConfiguration.model_validate(self.app or {})
        if self.search_recent_tweets_event:
            logger.warning(
                "search_recent_tweets_event is not used by the remote X module: "
                "each search run maps the envelopes it saved, and "
                "search_recent_tweets_files schedules reprocess_tweet_envelopes "
                "for the others. Remove %s.",
                [entry.name for entry in self.search_recent_tweets_event],
            )
