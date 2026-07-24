import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Annotated, Protocol

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
        "save_every_pages",
        "save_every_tweets",
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
    daily_max_tweets: int | None = None
    daily_max_usd: float | None = None
    monthly_max_tweets: int | None = None
    monthly_max_usd: float | None = None
    # Flush a new envelope whenever either threshold is hit during pagination
    # (whichever comes first). None disables that threshold; when both are None
    # the integration writes a single envelope at the end (legacy behaviour).
    save_every_pages: int | None = 10
    save_every_tweets: int | None = 1000


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
        dict | None,
        Field(
            default_factory=dict,
            description=(
                "Optional keyword arguments forwarded to "
                "XIntegration.search_recent_tweets for every query — any subset "
                "of: start_time, end_time, until_id, max_results, sort_order, "
                "tweet_fields, expansions, media_fields, poll_fields, "
                "user_fields, place_fields, max_pages, save_every_pages, "
                "save_every_tweets. 'since_id' is not accepted here; it is "
                "derived per query from the datastore."
            ),
            examples=[
                {
                    "max_results": 100,
                    "sort_order": "recency",
                    "max_pages": None,
                    "save_every_pages": 10,
                    "save_every_tweets": 1000,
                }
            ],
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
    daily_max_tweets: int | None
    daily_max_usd: float | None
    monthly_max_tweets: int | None
    monthly_max_usd: float | None

    def _tweet_cap(
        self, max_tweets: int | None, max_usd: float | None
    ) -> int | None:
        caps: list[int] = []
        if max_tweets is not None:
            caps.append(int(max_tweets))
        if max_usd is not None and self.cost_per_tweet_usd > 0:
            # Floor (tweets can't be fractional), with a tiny epsilon so float
            # artefacts don't turn an exact $0.50 / $0.005 = 100 into 99.
            caps.append(int(max_usd / self.cost_per_tweet_usd + 1e-9))
        return min(caps) if caps else None

    @property
    def daily_tweet_cap(self) -> int | None:
        return self._tweet_cap(self.daily_max_tweets, self.daily_max_usd)

    @property
    def monthly_tweet_cap(self) -> int | None:
        return self._tweet_cap(self.monthly_max_tweets, self.monthly_max_usd)


class _BudgetLedgerStorage(Protocol):
    def get_json(self, dir_path: str, file_name: str) -> dict: ...

    def save_json(
        self, data: dict | list, dir_path: str, file_name: str, copy: bool = True
    ) -> tuple[str, str]: ...


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
        storage_utils: _BudgetLedgerStorage,
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
        now = datetime.now(UTC)
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

    def exhausted_reason(self) -> str | None:
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
    Results are fetched newest-first (recency). The workflow — not the
    integration — writes envelope JSON files, flushing every
    ``save_every_pages`` / ``save_every_tweets`` (whichever hits first). The
    first page of a fresh ``since_id`` walk has **no** ``until_id`` (so X
    returns the newest tweets); after each saved batch, if more pages remain
    above ``since_id``, the next fetch keeps the same ``since_id`` and sets
    ``until_id=<oldest id of that batch>``. Recents are fetched before any
    incomplete older-page resume so a capped ``max_pages`` tick never spends
    its whole budget walking backwards.

    Queries are processed concurrently, one worker thread per query, so a batch
    of N queries runs its N fetch passes in parallel.
    """

    __configuration: XSearchRecentTweetsWorkflowConfiguration
    __storage_utils: StorageUtils
    __budget: _XApiBudget

    # Keys owned by the workflow; not forwarded to XIntegration.
    _WORKFLOW_ONLY_OPTION_KEYS = frozenset({"save_every_pages", "save_every_tweets"})

    def __init__(self, configuration: XSearchRecentTweetsWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__storage_utils = StorageUtils(self.__configuration.object_storage)
        # Global spend ledger lives under <datastore_path>/_budget so it sits
        # next to (but never collides with) the per-query search_recent_tweets
        # envelopes this workflow writes.
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

    def _query_prefix(self, query: str) -> str:
        return os.path.join(
            self.__configuration.datastore_path,
            "search_recent_tweets",
            slugify_query(query),
        )

    def _iter_envelope_filenames(self, query: str) -> list[str]:
        """Envelope basenames for *query*, newest filename first."""
        prefix = self._query_prefix(query)
        try:
            objects = self.__configuration.object_storage.list_objects(prefix)
        except Exception:  # noqa: BLE001
            return []
        return sorted(
            (os.path.basename(o) for o in objects if o.endswith(".json")),
            reverse=True,
        )

    def _load_envelope(self, query: str, filename: str) -> dict:
        data = self.__storage_utils.get_json(self._query_prefix(query), filename)
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _as_dict(value: object) -> dict:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _envelope_newest_id(data: dict) -> str | None:
        batch = XSearchRecentTweetsWorkflow._as_dict(data.get("batch"))
        if batch.get("newest_id"):
            return str(batch["newest_id"])
        results = XSearchRecentTweetsWorkflow._as_dict(data.get("results"))
        meta = XSearchRecentTweetsWorkflow._as_dict(results.get("meta"))
        newest_id = meta.get("newest_id")
        return str(newest_id) if newest_id else None

    @staticmethod
    def _envelope_oldest_id(data: dict) -> str | None:
        batch = XSearchRecentTweetsWorkflow._as_dict(data.get("batch"))
        if batch.get("oldest_id"):
            return str(batch["oldest_id"])
        results = XSearchRecentTweetsWorkflow._as_dict(data.get("results"))
        meta = XSearchRecentTweetsWorkflow._as_dict(results.get("meta"))
        oldest_id = meta.get("oldest_id")
        return str(oldest_id) if oldest_id else None

    def get_since_id(self, query: str) -> str | None:
        """Return the highest tweet id already fetched for ``query``, or None.

        Scans every envelope under
        ``<datastore_path>/search_recent_tweets/<slug>/`` and returns the max
        ``newest_id`` (tweet ids are snowflakes — lexicographic max works).
        Taking the max — not the newest file — is required once a run can write
        multiple batch files (later files may hold older pages).
        """
        best: str | None = None
        for filename in self._iter_envelope_filenames(query):
            newest_id = self._envelope_newest_id(self._load_envelope(query, filename))
            if not newest_id:
                continue
            if best is None or newest_id > best:
                best = newest_id
        return best

    def get_resume_until_id(self, query: str) -> str | None:
        """Oldest id to continue from when the latest envelope has ``has_more``.

        After a crash mid-pagination the newest file still reports
        ``batch.has_more=True``. The next run resumes older pages with
        ``until_id=<that oldest_id>`` so already-saved batches are kept.
        """
        filenames = self._iter_envelope_filenames(query)
        if not filenames:
            return None
        latest = self._load_envelope(query, filenames[0])
        batch = self._as_dict(latest.get("batch"))
        if not batch.get("has_more"):
            return None
        return self._envelope_oldest_id(latest)

    def get_resume_since_id(self, query: str) -> str | None:
        """``options.since_id`` from the latest incomplete envelope, if any."""
        filenames = self._iter_envelope_filenames(query)
        if not filenames:
            return None
        latest = self._load_envelope(query, filenames[0])
        batch = self._as_dict(latest.get("batch"))
        if not batch.get("has_more"):
            return None
        options = self._as_dict(latest.get("options"))
        since_id = options.get("since_id")
        return str(since_id) if since_id else None

    def _resolve_save_thresholds(self, options: dict) -> tuple[int | None, int | None]:
        save_every_pages = (
            options.get("save_every_pages", self.__configuration.save_every_pages)
        )
        save_every_tweets = (
            options.get("save_every_tweets", self.__configuration.save_every_tweets)
        )
        return save_every_pages, save_every_tweets

    @staticmethod
    def _batch_max_pages(
        save_every_pages: int | None,
        save_every_tweets: int | None,
        max_results: int,
    ) -> int | None:
        """Pages per integration call from the configured flush thresholds.

        Returns ``None`` when both thresholds are unset (legacy: one call uses
        the caller's ``max_pages`` as-is).
        """
        limits: list[int] = []
        if save_every_pages is not None:
            limits.append(int(save_every_pages))
        if save_every_tweets is not None:
            per_page = max(int(max_results), 1)
            limits.append(max(1, (int(save_every_tweets) + per_page - 1) // per_page))
        return min(limits) if limits else None

    def _save_envelope(
        self,
        *,
        query: str,
        options: dict,
        results: dict,
        has_more: bool,
        pages: int,
        started_at: str,
        ended_at: str,
    ) -> dict:
        """Persist one search envelope and return it (triggers ObjectPut)."""
        meta = self._as_dict(results.get("meta"))
        tweets = results.get("data") or []
        tweet_count = len(tweets) if isinstance(tweets, list) else 0
        envelope_dir = self._query_prefix(query)
        envelope_filename = (
            f"{datetime.now(UTC).isoformat()}_{slugify_query(query)}.json"
        )
        file_path = os.path.join(envelope_dir, envelope_filename)
        stored_options = {
            k: v
            for k, v in options.items()
            if k not in self._WORKFLOW_ONLY_OPTION_KEYS and v is not None
        }
        envelope = {
            "query": query,
            "options": stored_options,
            "results": results,
            "started_at": started_at,
            "ended_at": ended_at,
            "file_path": file_path,
            "batch": {
                "pages": pages,
                "tweet_count": tweet_count,
                "has_more": has_more,
                "newest_id": meta.get("newest_id"),
                "oldest_id": meta.get("oldest_id"),
            },
        }
        self.__storage_utils.save_json(
            envelope, envelope_dir, envelope_filename, copy=False
        )
        logger.info(
            "XSearchRecentTweetsWorkflow: saved envelope %s "
            "(%s tweets, %s pages, has_more=%s)",
            file_path,
            tweet_count,
            pages,
            has_more,
        )
        return envelope

    def _fetch_and_save_batches(
        self,
        query: str,
        *,
        base_options: dict,
        since_id: str | None,
        until_id: str | None,
        start_time: str | None,
        overall_max_pages: int | None,
        save_every_pages: int | None,
        save_every_tweets: int | None,
    ) -> tuple[list[str], list, str | None, int]:
        """Walk newest→older in batches.

        Returns ``(file_paths, tweets, newest_id, pages_used)``. The first call
        in a fresh ``since_id`` walk must pass ``until_id=None`` so X returns the
        newest tweets above ``since_id``; only later batches set
        ``until_id=<oldest id of the previous batch>``.
        """
        max_results = int(base_options.get("max_results") or 100)
        batch_pages = self._batch_max_pages(
            save_every_pages, save_every_tweets, max_results
        )

        file_paths: list[str] = []
        tweets: list = []
        newest_id: str | None = None
        pages_used = 0
        current_until_id = until_id

        while True:
            if overall_max_pages is not None and pages_used >= overall_max_pages:
                break

            call_max_pages = batch_pages
            if overall_max_pages is not None:
                remaining = overall_max_pages - pages_used
                call_max_pages = (
                    remaining
                    if call_max_pages is None
                    else min(call_max_pages, remaining)
                )
            if call_max_pages is not None and call_max_pages <= 0:
                break

            call_opts = {
                k: v
                for k, v in base_options.items()
                if k not in self._WORKFLOW_ONLY_OPTION_KEYS
                and k not in {"since_id", "until_id", "start_time", "max_pages"}
            }
            if since_id is not None:
                call_opts["since_id"] = since_id
            if current_until_id is not None:
                call_opts["until_id"] = current_until_id
            elif start_time is not None and since_id is None:
                call_opts["start_time"] = start_time
            if call_max_pages is not None:
                call_opts["max_pages"] = call_max_pages

            logger.info(
                "XSearchRecentTweetsWorkflow: query=%r since_id=%s until_id=%s "
                "max_pages=%s",
                query,
                since_id,
                current_until_id,
                call_max_pages,
            )
            started_at = datetime.now(UTC).isoformat()
            raw = self.__configuration.x_integration.search_recent_tweets(
                query,
                persist_envelope=False,
                **call_opts,
            )
            ended_at = datetime.now(UTC).isoformat()
            results = self._as_dict(raw.get("results"))
            meta = self._as_dict(results.get("meta"))
            batch_tweets = results.get("data") or []
            if not isinstance(batch_tweets, list):
                batch_tweets = []
            has_more = bool(meta.get("has_more"))
            pages_this = call_max_pages
            if pages_this is None:
                pages_this = max(1, (len(batch_tweets) + max_results - 1) // max_results) if batch_tweets else 0
            elif batch_tweets:
                pages_this = max(
                    1, min(pages_this, (len(batch_tweets) + max_results - 1) // max_results)
                )
            else:
                pages_this = 0

            envelope = self._save_envelope(
                query=query,
                options={**call_opts, "since_id": since_id, "until_id": current_until_id},
                results=results,
                has_more=has_more,
                pages=pages_this or 0,
                started_at=started_at,
                ended_at=ended_at,
            )
            if envelope.get("file_path"):
                file_paths.append(envelope["file_path"])
            tweets.extend(batch_tweets)
            # Keep the chronologically newest id seen in this walk (first batch).
            if meta.get("newest_id") and (
                newest_id is None or str(meta["newest_id"]) > newest_id
            ):
                newest_id = str(meta["newest_id"])

            pages_used += pages_this or (call_max_pages or 0)

            if not batch_tweets or not has_more:
                break
            oldest_id = meta.get("oldest_id")
            if not oldest_id:
                break
            # Next batch: same since_id window, walk older via until_id.
            current_until_id = str(oldest_id)

        return file_paths, tweets, newest_id, pages_used

    def _process_query(self, query: str, options: dict) -> dict:
        """Fetch one query incrementally; workflow persists batched envelopes.

        Order matters: **recents first**, then resume any incomplete older walk.

        1. Fetch tweets newer than the max stored ``newest_id`` via ``since_id``
           only (no ``until_id`` on the first page — an upper bound would skip
           the newest tweets and walk older ones instead). Flush every
           ``save_every_pages`` / ``save_every_tweets``; later pages of this
           walk add ``until_id=<oldest id of the previous batch>``.
        2. If budget remains and the latest envelope still has
           ``batch.has_more``, resume older pages with ``until_id`` + that
           envelope's ``since_id``.
        """
        save_every_pages, save_every_tweets = self._resolve_save_thresholds(options)
        overall_max_pages = options.get("max_pages")
        base_options = dict(options)

        file_paths: list[str] = []
        tweets: list = []
        newest_id: str | None = None
        pages_used = 0

        # --- Phase B first: incremental newer tweets via since_id -----------
        # Must run before the until_id resume. Otherwise a capped max_pages tick
        # spends its whole budget walking older tweets and never fetches recents.
        since_id = self.get_since_id(query)
        start_time = options.get("start_time")
        if since_id is None and not start_time:
            start_time = (datetime.now(UTC) - timedelta(hours=1)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

        logger.info(
            "XSearchRecentTweetsWorkflow: query=%r since_id=%s "
            "save_every_pages=%s save_every_tweets=%s",
            query,
            since_id,
            save_every_pages,
            save_every_tweets,
        )
        paths, batch_tweets, batch_newest, pages_b = self._fetch_and_save_batches(
            query,
            base_options=base_options,
            since_id=since_id,
            until_id=None,
            start_time=start_time,
            overall_max_pages=overall_max_pages,
            save_every_pages=save_every_pages,
            save_every_tweets=save_every_tweets,
        )
        file_paths.extend(paths)
        tweets.extend(batch_tweets)
        pages_used += pages_b
        if batch_newest:
            newest_id = batch_newest

        # --- Phase A: finish an interrupted older-pages walk ----------------
        remaining = None
        if overall_max_pages is not None:
            remaining = overall_max_pages - pages_used
            if remaining <= 0:
                return {
                    "query": query,
                    "since_id": since_id,
                    "new_count": len(tweets),
                    "newest_id": newest_id,
                    "file_path": file_paths[-1] if file_paths else None,
                    "file_paths": file_paths,
                    "tweets": tweets,
                }

        resume_until_id = self.get_resume_until_id(query)
        if resume_until_id is not None:
            resume_since = self.get_resume_since_id(query)
            logger.info(
                "XSearchRecentTweetsWorkflow: query=%r resuming older pages "
                "until_id=%s since_id=%s remaining_pages=%s",
                query,
                resume_until_id,
                resume_since,
                remaining,
            )
            paths, batch_tweets, batch_newest, pages_a = self._fetch_and_save_batches(
                query,
                base_options=base_options,
                since_id=resume_since,
                until_id=resume_until_id,
                start_time=None,
                overall_max_pages=remaining,
                save_every_pages=save_every_pages,
                save_every_tweets=save_every_tweets,
            )
            file_paths.extend(paths)
            tweets.extend(batch_tweets)
            pages_used += pages_a
            if batch_newest and (newest_id is None or batch_newest > newest_id):
                newest_id = batch_newest

        return {
            "query": query,
            "since_id": since_id,
            "new_count": len(tweets),
            "newest_id": newest_id,
            "file_path": file_paths[-1] if file_paths else None,
            "file_paths": file_paths,
            "tweets": tweets,
        }

    def run(self, parameters: XSearchRecentTweetsWorkflowParameters) -> dict:
        if not isinstance(parameters, XSearchRecentTweetsWorkflowParameters):
            raise TypeError(
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
    _default_start_time = (datetime.now(UTC) - timedelta(hours=24)).strftime(
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
