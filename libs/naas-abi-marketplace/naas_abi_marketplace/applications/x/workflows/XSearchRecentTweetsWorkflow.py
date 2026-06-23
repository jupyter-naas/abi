import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Optional

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_core.workflow.workflow import (
    Workflow,
    WorkflowConfiguration,
    WorkflowParameters,
)
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegration,
    slugify_query,
)
from pydantic import Field
from rdflib import URIRef

# Recognised keyword arguments accepted by XIntegration.search_recent_tweets,
# minus ``since_id`` which this workflow derives per query from the datastore.
_SEARCH_OPTION_KEYS = frozenset(
    {
        "start_time",
        "end_time",
        "until_id",
        "max_results",
        "sort_order",
        "tweet_fields",
        "expansions",
        "media_fields",
        "poll_fields",
        "user_fields",
        "place_fields",
        "max_pages",
    }
)


@dataclass
class XSearchRecentTweetsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for XSearchRecentTweetsWorkflow.

    Attributes:
        x_integration: The XIntegration used to call the X v2 recent-search
            endpoint. Its responses are persisted to the datastore, which is
            what makes incremental (since_id) runs possible.
        object_storage: Service used to read previously stored responses so the
            workflow can recover each query's ``since_id``.
        triple_store: Engine triple store, retained for callers that wire it
            explicitly. Defaults to the engine's triple store.
        datastore_path: Object-storage prefix under which the integration writes
            ``search_recent_tweets/<slug>/<timestamp>_<slug>.json`` files.
        graph_name: Named graph associated with this workflow's data.
    """

    x_integration: XIntegration
    object_storage: ObjectStorageService
    triple_store: TripleStoreService = field(
        default_factory=lambda: ABIModule.get_instance().engine.services.triple_store
    )
    datastore_path: str = field(
        default_factory=lambda: ABIModule.get_instance().configuration.datastore_path
    )
    graph_name: URIRef = field(
        default_factory=lambda: URIRef(
            ABIModule.get_instance().configuration.graph_name
        )
    )
    # ----- X API spend guard (per filter) ------------------------------------
    # Caps are supplied per filter by the orchestration from
    # XTweetSearchWorkflowConfiguration (or by ad-hoc callers / the CLI). A cap
    # of None disables that limit; cost_per_tweet_usd converts USD caps into a
    # tweet count. ``budget_key`` keys the usage ledger so each filter tracks
    # and caps its own spend independently.
    budget_key: str = "default"
    cost_per_tweet_usd: float = 0.005
    daily_max_tweets: Optional[int] = None
    daily_max_usd: Optional[float] = None
    monthly_max_tweets: Optional[int] = None
    monthly_max_usd: Optional[float] = None


class XSearchRecentTweetsWorkflowParameters(WorkflowParameters):
    queries: Annotated[
        list[str],
        Field(
            ...,
            description=(
                "One or more X v2 search queries to run. Each query is fetched "
                "incrementally: the workflow looks up the highest tweet id "
                "already stored for that query (since_id) and only returns "
                "tweets newer than it."
            ),
            examples=[
                [
                    '("rogue drone" OR "drone threat") ("World Cup" OR "FIFA") lang:en -is:retweet',
                    '("unauthorized drone" OR "airspace violation") ("stadium") lang:en -is:retweet',
                ]
            ],
        ),
    ]
    options: Annotated[
        Optional[dict],
        Field(
            default_factory=dict,
            description=(
                "Optional keyword arguments forwarded to "
                "XIntegration.search_recent_tweets for every query — any subset "
                "of: start_time, end_time, until_id, max_results, sort_order, "
                "tweet_fields, expansions, media_fields, poll_fields, "
                "user_fields, place_fields, max_pages. 'since_id' is not "
                "accepted here; it is derived per query from the datastore."
            ),
            examples=[{"max_results": 100, "sort_order": "recency", "max_pages": None}],
        ),
    ]
    persist: Annotated[
        bool,
        Field(
            description=(
                "Whether the per-query pipeline inserts the generated tweet "
                "graph into the configured triple store. Set False to fetch and "
                "persist the JSON envelopes (and build the graphs) without "
                "writing to the triple store."
            ),
        ),
    ] = True


@dataclass
class _BudgetLimits:
    """Resolved spend caps for the X recent-search workflow.

    A cap can be given as a tweet count, a USD amount, or both. USD caps are
    converted to a tweet count via ``cost_per_tweet_usd``; when both are set for
    the same period the more restrictive (smaller) tweet count wins. ``None``
    on both inputs means that period is uncapped.
    """

    cost_per_tweet_usd: float
    daily_max_tweets: Optional[int]
    daily_max_usd: Optional[float]
    monthly_max_tweets: Optional[int]
    monthly_max_usd: Optional[float]

    def _tweet_cap(
        self, max_tweets: Optional[int], max_usd: Optional[float]
    ) -> Optional[int]:
        caps: list[int] = []
        if max_tweets is not None:
            caps.append(int(max_tweets))
        if max_usd is not None and self.cost_per_tweet_usd > 0:
            # Floor (tweets can't be fractional), with a tiny epsilon so float
            # artefacts don't turn an exact $0.50 / $0.005 = 100 into 99.
            caps.append(int(max_usd / self.cost_per_tweet_usd + 1e-9))
        return min(caps) if caps else None

    @property
    def daily_tweet_cap(self) -> Optional[int]:
        return self._tweet_cap(self.daily_max_tweets, self.daily_max_usd)

    @property
    def monthly_tweet_cap(self) -> Optional[int]:
        return self._tweet_cap(self.monthly_max_tweets, self.monthly_max_usd)


class _XApiBudget:
    """Persistent global ledger of tweets retrieved per day and per month.

    Each filter keeps its own ledger, a single JSON object in object storage at
    ``<budget_path>/<budget_key>.json``::

        {"daily": {"2026-06-22": 1234}, "monthly": {"2026-06": 56789}}

    Counts are tweets (the billed X 'resource'); USD is derived on read via
    ``cost_per_tweet_usd``. The guard is all-or-nothing: if *either* the daily
    or monthly cap has already been reached, :meth:`exhausted_reason` returns a
    message and the caller fetches nothing; otherwise it runs and afterwards
    calls :meth:`record` with the number of tweets actually retrieved.

    Read-modify-write is not atomic across processes, but the XOrchestration
    runs each filter's job in-process and skips ticks while a run is in flight,
    so concurrent writers are not expected. A small overshoot (one tick's worth)
    is acceptable for a soft spend guard.
    """

    # Keep the ledger from growing without bound: retain at most this many of
    # the most recent day / month buckets on each write.
    _MAX_DAILY_BUCKETS = 90
    _MAX_MONTHLY_BUCKETS = 24

    def __init__(
        self,
        storage_utils: StorageUtils,
        budget_path: str,
        budget_key: str,
        limits: _BudgetLimits,
    ):
        self._storage = storage_utils
        self._path = budget_path
        # One ledger file per filter so each tracks/caps its own spend.
        self._ledger_filename = f"{slugify_query(budget_key) or 'default'}.json"
        self._limits = limits

    @staticmethod
    def _period_keys() -> tuple[str, str]:
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")

    def _load(self) -> dict:
        # StorageUtils.get_json returns {} when the ledger does not exist yet.
        data = self._storage.get_json(self._path, self._ledger_filename) or {}
        if not isinstance(data.get("daily"), dict):
            data["daily"] = {}
        if not isinstance(data.get("monthly"), dict):
            data["monthly"] = {}
        return data

    def usage(self) -> tuple[int, int]:
        """Return ``(tweets_today, tweets_this_month)`` from the ledger."""
        data = self._load()
        day_key, month_key = self._period_keys()
        return (
            int(data["daily"].get(day_key, 0)),
            int(data["monthly"].get(month_key, 0)),
        )

    def exhausted_reason(self) -> Optional[str]:
        """Return a human-readable reason if a cap is reached, else None."""
        used_day, used_month = self.usage()
        cost = self._limits.cost_per_tweet_usd
        day_cap = self._limits.daily_tweet_cap
        month_cap = self._limits.monthly_tweet_cap
        if day_cap is not None and used_day >= day_cap:
            return (
                f"daily X budget reached: {used_day}/{day_cap} tweets "
                f"(~${used_day * cost:.2f}) already retrieved today"
            )
        if month_cap is not None and used_month >= month_cap:
            return (
                f"monthly X budget reached: {used_month}/{month_cap} tweets "
                f"(~${used_month * cost:.2f}) already retrieved this month"
            )
        return None

    def record(self, tweets_retrieved: int) -> None:
        """Add ``tweets_retrieved`` to today's and this month's counters."""
        if tweets_retrieved <= 0:
            return
        data = self._load()
        day_key, month_key = self._period_keys()
        data["daily"][day_key] = int(data["daily"].get(day_key, 0)) + tweets_retrieved
        data["monthly"][month_key] = (
            int(data["monthly"].get(month_key, 0)) + tweets_retrieved
        )
        data["daily"] = self._prune(data["daily"], self._MAX_DAILY_BUCKETS)
        data["monthly"] = self._prune(data["monthly"], self._MAX_MONTHLY_BUCKETS)
        self._storage.save_json(
            data, self._path, self._ledger_filename, copy=False
        )

    @staticmethod
    def _prune(buckets: dict, keep: int) -> dict:
        if len(buckets) <= keep:
            return buckets
        # Keys are sortable ISO date / month strings; keep the most recent.
        newest = sorted(buckets)[-keep:]
        return {k: buckets[k] for k in newest}

    def snapshot(self) -> dict:
        """Current usage + caps, suitable for returning to callers / logs."""
        used_day, used_month = self.usage()
        cost = self._limits.cost_per_tweet_usd
        return {
            "tweets_today": used_day,
            "tweets_this_month": used_month,
            "usd_today": round(used_day * cost, 4),
            "usd_this_month": round(used_month * cost, 4),
            "daily_tweet_cap": self._limits.daily_tweet_cap,
            "monthly_tweet_cap": self._limits.monthly_tweet_cap,
            "cost_per_tweet_usd": cost,
        }


class XSearchRecentTweetsWorkflow(Workflow[XSearchRecentTweetsWorkflowParameters]):
    """Run several X recent-search queries incrementally.

    For every query the workflow recovers a ``since_id`` from the datastore (the
    highest tweet id seen on a previous run) and asks X only for newer tweets.
    The integration persists each response, so the cursor advances on its own:
    the first run fetches the last 7 days, and every subsequent run returns only
    what appeared since. ``since_id`` is read by scanning the per-query folder
    newest-to-oldest and taking the first ``results.meta.newest_id`` found, so a
    run that returned zero new tweets (no ``newest_id``) does not reset it.

    Queries are processed concurrently, one worker thread per query, so a batch
    of N queries runs its N fetch passes in parallel.
    """

    __configuration: XSearchRecentTweetsWorkflowConfiguration
    __storage_utils: StorageUtils
    __budget: _XApiBudget

    def __init__(self, configuration: XSearchRecentTweetsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__storage_utils = StorageUtils(self.__configuration.object_storage)
        # Global spend ledger lives under <datastore_path>/_budget so it sits
        # next to (but never collides with) the per-query search_recent_tweets
        # envelopes the integration writes.
        self.__budget = _XApiBudget(
            self.__storage_utils,
            os.path.join(self.__configuration.datastore_path, "_budget"),
            self.__configuration.budget_key,
            _BudgetLimits(
                cost_per_tweet_usd=self.__configuration.cost_per_tweet_usd,
                daily_max_tweets=self.__configuration.daily_max_tweets,
                daily_max_usd=self.__configuration.daily_max_usd,
                monthly_max_tweets=self.__configuration.monthly_max_tweets,
                monthly_max_usd=self.__configuration.monthly_max_usd,
            ),
        )

    def get_since_id(self, query: str) -> Optional[str]:
        """Return the highest tweet id already fetched for ``query``, or None.

        Scans ``<datastore_path>/search_recent_tweets/<slug>/`` from the newest
        file to the oldest and returns the first ``results.meta.newest_id`` it
        finds. Returns None on the first run for a query (no folder yet).
        """
        prefix = os.path.join(
            self.__configuration.datastore_path,
            "search_recent_tweets",
            slugify_query(query),
        )
        try:
            objects = self.__configuration.object_storage.list_objects(prefix)
        except Exception:
            return None

        filenames = sorted(
            (os.path.basename(o) for o in objects if o.endswith(".json")),
            reverse=True,
        )
        for filename in filenames:
            data = self.__storage_utils.get_json(prefix, filename)
            results = data.get("results") if isinstance(data, dict) else None
            meta = results.get("meta") if isinstance(results, dict) else None
            newest_id = meta.get("newest_id") if isinstance(meta, dict) else None
            if newest_id:
                return newest_id
        return None

    def _process_query(self, query: str, options: dict) -> dict:
        """Fetch one query incrementally and persist its JSON envelope.

        Recovers the query's ``since_id`` and calls the X v2 search endpoint,
        which writes the ``{query, options, results, …}`` envelope to object
        storage. Runs in its own worker thread.
        """
        since_id = self.get_since_id(query)

        # On the first run for a query there is no since_id to anchor the window,
        # so default start_time to 1 hour ago (unless the caller set it). With a
        # since_id, X already returns only newer tweets, so no default is needed.
        if since_id is None and not options.get("start_time"):
            options = {
                **options,
                "start_time": (
                    datetime.now(timezone.utc) - timedelta(hours=1)
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

        logger.info(f"XSearchRecentTweetsWorkflow: query={query!r} since_id={since_id}")
        envelope = self.__configuration.x_integration.search_recent_tweets(
            query, since_id=since_id, **options
        )
        results = envelope.get("results") or {}
        tweets = results.get("data") or []
        newest_id = (results.get("meta") or {}).get("newest_id")
        file_path = envelope.get("file_path")

        return {
            "query": query,
            "since_id": since_id,
            "new_count": len(tweets),
            "newest_id": newest_id,
            "file_path": file_path,
            "tweets": tweets,
        }

    def run(self, parameters: XSearchRecentTweetsWorkflowParameters) -> dict:
        if not isinstance(parameters, XSearchRecentTweetsWorkflowParameters):
            raise ValueError(
                "Parameters must be of type XSearchRecentTweetsWorkflowParameters"
            )

        options: dict = parameters.options or {}
        unknown = set(options) - _SEARCH_OPTION_KEYS
        if unknown:
            raise ValueError(
                f"Unknown options for search_recent_tweets: {sorted(unknown)}. "
                f"Accepted keys: {sorted(_SEARCH_OPTION_KEYS)} "
                "('since_id' is derived per query and cannot be set here)."
            )

        queries = parameters.queries
        if not queries:
            return {"total_new_tweets": 0, "results": []}

        # All-or-nothing spend guard: if the daily or monthly cap is already
        # reached, fetch nothing this tick (no X API call, so no spend) and let
        # the orchestration try again on its next interval. The counter resets
        # naturally — a new day / month is simply a new ledger bucket.
        blocked_reason = self.__budget.exhausted_reason()
        if blocked_reason is not None:
            logger.warning(
                f"XSearchRecentTweetsWorkflow: skipping fetch — {blocked_reason}"
            )
            return {
                "total_new_tweets": 0,
                "results": [],
                "budget_blocked": True,
                "budget_reason": blocked_reason,
                "budget": self.__budget.snapshot(),
            }

        # One worker thread per query, as requested — each thread fetches its
        # query independently. ``ThreadPoolExecutor.map`` preserves input order,
        # so ``results`` lines up with ``queries``.
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            results = list(
                executor.map(
                    lambda query: self._process_query(query, options),
                    queries,
                )
            )

        total_new = sum(item["new_count"] for item in results)
        # Charge the budget for every tweet ('resource') actually retrieved so
        # the next tick sees the updated spend.
        self.__budget.record(total_new)
        return {
            "total_new_tweets": total_new,
            "results": results,
            "budget_blocked": False,
            "budget": self.__budget.snapshot(),
        }

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="x_search_recent_tweets_incremental",
                description=(
                    "Run one or more X v2 recent-search queries incrementally, "
                    "in parallel (one worker thread per query). Each query is "
                    "resumed from the highest tweet id already stored for it "
                    "(since_id), so only tweets newer than the previous run are "
                    "returned. Returns, per query, the new tweets, the next "
                    "cursor (newest_id) and the persisted envelope file_path."
                ),
                func=lambda **kwargs: self.run(
                    XSearchRecentTweetsWorkflowParameters(**kwargs)
                ),
                args_schema=XSearchRecentTweetsWorkflowParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None


if __name__ == "__main__":
    """Command-line entry point for XSearchRecentTweetsWorkflow.

    Every argument has a default, so the workflow runs with no flags:

    ```
    abi dev up
    OXIGRAPH_URL=http://127.0.0.1:8432 uv run python \
        libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/workflows/XSearchRecentTweetsWorkflow.py
    ```

    Override any of them, e.g.:

    ```
    ... XSearchRecentTweetsWorkflow.py \
        --queries '("FIFA World Cup") lang:en -is:retweet' \
        --max-results 50 --sort-order relevancy --no-persist
    ```
    """
    import argparse

    from naas_abi_core.engine.Engine import Engine

    parser = argparse.ArgumentParser(
        description=(
            "Run one or more X v2 recent-search queries incrementally and map "
            "the results into the knowledge graph."
        )
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        default=[
            "(FIFA World Cup) has:media lang:en -is:retweet",
        ],
        help="One or more X v2 search queries to run incrementally.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Tweets per page requested from X (10-100). Default: 100.",
    )
    parser.add_argument(
        "--sort-order",
        default="recency",
        choices=["recency", "relevancy"],
        help="Order results are returned in. Default: recency.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Max pages to fetch per query. Default: None (exhaust all new tweets).",
    )
    _default_start_time = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    parser.add_argument(
        "--start-time",
        default=_default_start_time,
        help="Oldest UTC timestamp (YYYY-MM-DDTHH:mm:ssZ), inclusive. "
        "Defaults to 24 hours before script start time if unset.",
    )
    parser.add_argument(
        "--end-time",
        default=None,
        help="Newest UTC timestamp (ISO 8601) to search to. Default: None.",
    )
    parser.add_argument(
        "--until-id",
        default=None,
        help="Return tweets older than this tweet id. Default: None.",
    )
    parser.add_argument(
        "--persist",
        dest="persist",
        action="store_true",
        default=True,
        help="Insert the generated tweet graph into the triple store (default).",
    )
    parser.add_argument(
        "--no-persist",
        dest="persist",
        action="store_false",
        help="Fetch and graph without writing to the triple store.",
    )
    args = parser.parse_args()

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.x"])

    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegrationConfiguration,
    )

    bearer_token = engine.services.secret.get("X_BEARER_TOKEN")
    datastore_path = ABIModule.get_instance().configuration.datastore_path

    x_integration = XIntegration(
        XIntegrationConfiguration(
            bearer_token=bearer_token, datastore_path=datastore_path
        )
    )

    workflow = XSearchRecentTweetsWorkflow(
        XSearchRecentTweetsWorkflowConfiguration(
            x_integration=x_integration,
            object_storage=engine.services.object_storage,
            datastore_path=datastore_path,
        )
    )

    # Only forward options the user actually set, so unset ones keep the X API
    # defaults rather than being sent as null.
    options: dict = {
        "max_results": args.max_results,
        "sort_order": args.sort_order,
        "max_pages": args.max_pages,
    }
    if args.start_time is not None:
        options["start_time"] = args.start_time
    if args.end_time is not None:
        options["end_time"] = args.end_time
    if args.until_id is not None:
        options["until_id"] = args.until_id

    output = workflow.run(
        XSearchRecentTweetsWorkflowParameters(
            queries=args.queries,
            options=options,
            persist=args.persist,
        )
    )

    for item in output["results"]:
        cursor = item["since_id"] or "none (first run)"
        print(
            f"[{item['query'][:60]}…] since_id={cursor} → "
            f"{item['new_count']} new tweets"
        )
        if item["newest_id"]:
            print(f"  Next since_id: {item['newest_id']}")

    print(f"Total new tweets: {output['total_new_tweets']}")
