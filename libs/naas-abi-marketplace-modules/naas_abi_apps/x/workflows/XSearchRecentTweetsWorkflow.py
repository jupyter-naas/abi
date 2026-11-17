"""Fetch X recent-search queries incrementally, under per-filter spend caps.

Port of the in-engine ``XSearchRecentTweetsWorkflow`` without core: the same
``since_id`` cursor, batched envelopes, spend ledger (daily and monthly caps per
filter, USD converted at ``cost_per_tweet_usd``) and partial-failure accounting.

A plain class, not an SDK ``Workflow``: its ``run`` is synchronous (it runs in a
worker thread, called by ``flows/common.py``), and the SDK would publish a
``Workflow`` subclass found under ``workflows/`` as ``workflow.<slug>``. Object
storage is the blocking ``SyncService`` (``module.engine.services.object_storage``
of a ``services.SyncModule``), and the async ``XIntegration`` is called through
``run`` (``SyncModule.run``), which runs a coroutine on the module's loop::

    workflow = XSearchRecentTweetsWorkflow(
        XSearchRecentTweetsWorkflowConfiguration(
            x_integration=x_integration_for(sync),  # integrations.XIntegration
            object_storage=sync.engine.services.object_storage,
            run=sync.run,
            datastore_path=sync.configuration.datastore_path,
            budget_key=filter_config.name,
            ...,  # caps and save thresholds of the filter
        )
    )
    output = workflow.run(XSearchRecentTweetsWorkflowParameters(queries=[query]))

``search_with_budget`` and ``read_with_budget`` put one call of the agent's
tools through a ledger: the allowance is reserved before X is called, and the
call fetches no more pages than the caps leave.
"""

import math
import os
import threading
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Protocol

from naas_abi_apps.x.integrations.XIntegration import (
    XIntegration,
    page_resources,
    slugify_query,
)
from naas_abi_apps.x.services import StorageUtils, logger
from pydantic import BaseModel, Field

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
class XSearchRecentTweetsWorkflowConfiguration:
    """Configuration for XSearchRecentTweetsWorkflow.

    Attributes:
        x_integration: The async XIntegration used to call the X v2 recent-search
            endpoint.
        object_storage: The blocking object storage (``SyncService``) the
            workflow writes envelopes, cursors and the ledger to.
        run: Runs a coroutine to completion from the calling (worker) thread:
            ``SyncModule.run``. Every X API call goes through it.
        triple_store: Not used; kept for callers that pass it.
        datastore_path: Object-storage prefix of
            ``search_recent_tweets/<slug>/<timestamp>_<slug>.json``, ``_cursors/``
            and ``_budget/`` (the module's ``datastore_path``).
        graph_name: Named graph associated with this workflow's data.
    """

    x_integration: XIntegration
    object_storage: Any
    run: Callable[[Awaitable[Any]], Any]
    triple_store: Any = None
    datastore_path: str = "x"
    graph_name: str = "http://ontology.naas.ai/graph/x"
    # ----- X API spend guard (per filter) ------------------------------------
    # Caps are supplied per filter by the search flow from
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


class XSearchRecentTweetsWorkflowParameters(BaseModel):
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

    def _tweet_cap(self, max_tweets: int | None, max_usd: float | None) -> int | None:
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

    def remaining_tweets(self, used_day: int, used_month: int) -> int | None:
        """Tweets left under the most restrictive cap (``None``: uncapped)."""
        left = [
            cap - used
            for cap, used in (
                (self.daily_tweet_cap, used_day),
                (self.monthly_tweet_cap, used_month),
            )
            if cap is not None
        ]
        return max(0, min(left)) if left else None


# One lock per ledger file, for the check, the reservation and the record of
# every ledger on it in this process. A replica hosts the module in a single
# process, so this serialises all of its writers; two replicas sharing the
# object storage can still interleave a load / save of the same ledger (a
# bounded overshoot): no distributed lock is taken.
_LEDGER_LOCKS: dict[str, threading.Lock] = {}
_LEDGER_LOCKS_GUARD = threading.Lock()


def _ledger_lock(key: str) -> threading.Lock:
    with _LEDGER_LOCKS_GUARD:
        lock = _LEDGER_LOCKS.get(key)
        if lock is None:
            lock = _LEDGER_LOCKS[key] = threading.Lock()
        return lock


@dataclass(frozen=True)
class Reservation:
    """What :meth:`_XApiBudget.reserve` added to the ledger for one call:
    ``tweets`` (the most the call can bill) in the day and month it was made,
    and the ``max_pages`` the call may fetch."""

    tweets: int
    max_pages: int
    day_key: str
    month_key: str


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

    The agent's calls instead :meth:`reserve` the most they can bill before
    they call X (limited to what the caps leave), then :meth:`settle` the
    reservation to what X billed: parallel tool calls see each other's spend.

    Every load / add / save holds the ledger's lock (``_ledger_lock``), so
    writers of one process never lose an update. The lock is per process: a
    filter's runs are serialised by ``skip_if_running``, but two replicas
    sharing the object storage could still interleave (see ``_LEDGER_LOCKS``).
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
        self._lock = _ledger_lock(os.path.join(budget_path, self._ledger_filename))

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

    def _add(self, tweets: int, day_key: str, month_key: str) -> None:
        """Add ``tweets`` (negative: give back, never below zero) to the
        ``day_key`` and ``month_key`` counters. The caller holds the lock."""
        data = self._load()
        data["daily"][day_key] = max(0, int(data["daily"].get(day_key, 0)) + tweets)
        data["monthly"][month_key] = max(
            0, int(data["monthly"].get(month_key, 0)) + tweets
        )
        data["daily"] = self._prune(data["daily"], self._MAX_DAILY_BUCKETS)
        data["monthly"] = self._prune(data["monthly"], self._MAX_MONTHLY_BUCKETS)
        self._storage.save_json(data, self._path, self._ledger_filename, copy=False)

    def record(self, tweets_retrieved: int) -> None:
        """Add ``tweets_retrieved`` to today's and this month's counters."""
        if tweets_retrieved <= 0:
            return
        with self._lock:
            self._add(tweets_retrieved, *self._period_keys())

    def reserve(self, max_pages: int, max_results: int) -> Reservation | str:
        """Before a call to X: the reason a cap forbids it, or its reservation.

        Under the ledger's lock: when no cap is reached, ``max_pages`` is
        limited to the allowance the caps leave (``ceil(remaining /
        max_results)`` pages, the most restrictive cap winning; the last page
        may cross the cap by less than one page), and the most the call can
        bill (``pages * max_results``) is added to the ledger at once, so that
        a parallel call sees it. :meth:`settle` corrects it afterwards.
        """
        per_page = max(1, int(max_results))
        with self._lock:
            reason = self.exhausted_reason()
            if reason is not None:
                return reason
            pages = max(1, int(max_pages))
            remaining = self._limits.remaining_tweets(*self.usage())
            if remaining is not None:
                pages = min(pages, max(1, math.ceil(remaining / per_page)))
            day_key, month_key = self._period_keys()
            reservation = Reservation(pages * per_page, pages, day_key, month_key)
            self._add(reservation.tweets, day_key, month_key)
            return reservation

    def settle(self, reservation: Reservation, billed: int) -> None:
        """Replace ``reservation`` by the ``billed`` tweets X returned, in the
        day and month the reservation was made."""
        delta = int(billed) - reservation.tweets
        if delta == 0:
            return
        with self._lock:
            self._add(delta, reservation.day_key, reservation.month_key)

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


class XSearchRecentTweetsWorkflow:
    """Run several X recent-search queries incrementally.

    For every query the workflow reads a ``since_id`` from that query's cursor
    in the datastore (the highest tweet id seen on a previous run, rebuilt by
    scanning the envelopes when absent) and asks X only for newer tweets.
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

    # Bumped when the cursor payload shape changes: an older/newer cursor is
    # ignored and rebuilt from the envelopes rather than misread.
    _CURSOR_VERSION = 1

    def __init__(self, configuration: XSearchRecentTweetsWorkflowConfiguration):
        self.__configuration = configuration
        self.__storage_utils = StorageUtils(self.__configuration.object_storage)
        # Per-query since_id cursors, kept OUTSIDE search_recent_tweets/ so they
        # neither show up in the envelope scan nor raise ObjectPut events that
        # XSearchRecentTweetsEventOrchestration would try to map as envelopes.
        self.__cursor_path = os.path.join(
            self.__configuration.datastore_path, "_cursors"
        )
        self.__saved_file_paths: list[str] = []
        self.__saved_tweets = 0
        # Tweets of every page X answered (billed), saved in an envelope or not:
        # a batch that fails part-way was billed for its earlier pages.
        self.__billed_tweets = 0
        self.__billed_lock = threading.Lock()
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

    def saved_file_paths(self) -> list[str]:
        """Envelopes this instance has written so far, in order.

        A run that fails part-way (a rate limit on a later batch) has already saved
        the earlier batches, and its return value never reaches the caller: this
        is how the durable search flow still maps them.
        """
        return list(self.__saved_file_paths)

    def _count_billed_page(self, page: dict) -> None:
        """``on_page`` of the integration: count a page X answered. Runs on the
        loop of ``run`` (one per query thread in tests): only counts."""
        with self.__billed_lock:
            self.__billed_tweets += page_resources(page)

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

    # ----- since_id cursor ---------------------------------------------------
    #
    # Everything the next run needs to resume — the max ``newest_id`` ever seen
    # and the latest envelope's resume state — is kept in one small JSON file
    # per query at ``<datastore_path>/_cursors/<slug>.json``::
    #
    #     {"version": 1, "query": …, "newest_id": "…",
    #      "latest": {"filename": …, "has_more": false,
    #                 "oldest_id": "…", "since_id": "…"}}
    #
    # Without it every tick re-listed the query prefix three times and
    # downloaded *every* envelope ever written just to take a max snowflake id —
    # O(all envelopes) per run, growing forever (this filter writes up to one
    # envelope per page per tick). The cursor makes that O(1); the full scan
    # survives as the rebuild path, so a missing or unreadable cursor is a
    # one-off cost that heals itself rather than a correctness problem.

    def _cursor_filename(self, query: str) -> str:
        return f"{slugify_query(query) or 'default'}.json"

    def _load_cursor(self, query: str) -> dict | None:
        """Stored cursor for *query*, or None when absent/stale/unreadable."""
        try:
            data = self.__storage_utils.get_json(
                self.__cursor_path, self._cursor_filename(query)
            )
        except Exception:  # noqa: BLE001 — absent cursor → rebuild from envelopes
            return None
        if not isinstance(data, dict) or not data:
            return None
        if data.get("version") != self._CURSOR_VERSION:
            return None
        return data

    def _save_cursor(self, query: str, cursor: dict) -> None:
        """Persist *cursor*; a write failure only costs the next run a rescan."""
        try:
            self.__storage_utils.save_json(
                cursor, self.__cursor_path, self._cursor_filename(query), copy=False
            )
        except Exception as exc:  # noqa: BLE001 — never fail a fetch on the cursor
            logger.warning(
                f"XSearchRecentTweetsWorkflow: could not save since_id cursor for "
                f"query={query!r} ({exc}); the next run will rescan the envelopes"
            )

    @staticmethod
    def _cursor_from_envelope(
        newest_id: str | None, envelope: dict, filename: str, query: str
    ) -> dict:
        """Build the cursor payload naming *envelope* as the latest one."""
        batch = XSearchRecentTweetsWorkflow._as_dict(envelope.get("batch"))
        options = XSearchRecentTweetsWorkflow._as_dict(envelope.get("options"))
        since_id = options.get("since_id")
        return {
            "version": XSearchRecentTweetsWorkflow._CURSOR_VERSION,
            "query": query,
            "newest_id": newest_id,
            "latest": {
                "filename": filename,
                "has_more": bool(batch.get("has_more")),
                "oldest_id": XSearchRecentTweetsWorkflow._envelope_oldest_id(envelope),
                "since_id": str(since_id) if since_id else None,
            },
            "updated_at": datetime.now(UTC).isoformat(),
        }

    def _rebuild_cursor(self, query: str) -> dict:
        """Scan every envelope for *query* and write the cursor it implies.

        The max ``newest_id`` — not the newest file's — is what resumes the
        walk, because a run that writes several batch files puts *older* pages
        in the later ones. Resume state comes from the newest file only.
        """
        filenames = self._iter_envelope_filenames(query)
        newest_id: str | None = None
        latest_envelope: dict = {}
        for index, filename in enumerate(filenames):
            envelope = self._load_envelope(query, filename)
            if index == 0:
                latest_envelope = envelope
            candidate = self._envelope_newest_id(envelope)
            if candidate and (newest_id is None or candidate > newest_id):
                newest_id = candidate
        cursor = self._cursor_from_envelope(
            newest_id, latest_envelope, filenames[0] if filenames else "", query
        )
        logger.info(
            f"XSearchRecentTweetsWorkflow: rebuilt since_id cursor for "
            f"query={query!r} from {len(filenames)} envelope(s) "
            f"(newest_id={newest_id})"
        )
        self._save_cursor(query, cursor)
        return cursor

    def _cursor(self, query: str) -> dict:
        """The cursor for *query*, rebuilt from the envelopes when missing."""
        return self._load_cursor(query) or self._rebuild_cursor(query)

    def _advance_cursor(self, query: str, envelope: dict, filename: str) -> None:
        """Fold a just-saved *envelope* into the cursor.

        Called from :meth:`_save_envelope`, so the file written last in a run is
        the one the cursor names as latest — the same file the old
        newest-filename-first scan picked. ``newest_id`` only ever moves up, so
        the older pages a resume walk saves cannot drag it backwards.
        """
        cursor = self._load_cursor(query) or {}
        newest_id = cursor.get("newest_id")
        newest_id = str(newest_id) if newest_id else None
        candidate = self._envelope_newest_id(envelope)
        if candidate and (newest_id is None or candidate > newest_id):
            newest_id = candidate
        self._save_cursor(
            query, self._cursor_from_envelope(newest_id, envelope, filename, query)
        )

    def get_since_id(self, query: str) -> str | None:
        """Return the highest tweet id already fetched for ``query``, or None.

        Read from the per-query cursor (tweet ids are snowflakes, so the
        lexicographic max is the chronological one); the cursor is rebuilt by
        scanning the stored envelopes when it is missing.
        """
        newest_id = self._cursor(query).get("newest_id")
        return str(newest_id) if newest_id else None

    def get_resume_until_id(self, query: str) -> str | None:
        """Oldest id to continue from when the latest envelope has ``has_more``.

        After a crash mid-pagination the newest envelope still reports
        ``batch.has_more=True``. The next run resumes older pages with
        ``until_id=<that oldest_id>`` so already-saved batches are kept.
        """
        latest = self._as_dict(self._cursor(query).get("latest"))
        if not latest.get("has_more"):
            return None
        oldest_id = latest.get("oldest_id")
        return str(oldest_id) if oldest_id else None

    def get_resume_since_id(self, query: str) -> str | None:
        """``options.since_id`` from the latest incomplete envelope, if any."""
        latest = self._as_dict(self._cursor(query).get("latest"))
        if not latest.get("has_more"):
            return None
        since_id = latest.get("since_id")
        return str(since_id) if since_id else None

    def _resolve_save_thresholds(self, options: dict) -> tuple[int | None, int | None]:
        save_every_pages = options.get(
            "save_every_pages", self.__configuration.save_every_pages
        )
        save_every_tweets = options.get(
            "save_every_tweets", self.__configuration.save_every_tweets
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
        # Advance the cursor with the envelope just written, so the next run
        # resumes from it without re-reading the whole envelope archive.
        self._advance_cursor(query, envelope, envelope_filename)
        self.__saved_file_paths.append(file_path)
        self.__saved_tweets += tweet_count
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
            raw = self.__configuration.run(
                self.__configuration.x_integration.search_recent_tweets(
                    query,
                    persist_envelope=False,
                    on_page=self._count_billed_page,
                    **call_opts,
                )
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
                pages_this = (
                    max(1, (len(batch_tweets) + max_results - 1) // max_results)
                    if batch_tweets
                    else 0
                )
            elif batch_tweets:
                pages_this = max(
                    1,
                    min(
                        pages_this, (len(batch_tweets) + max_results - 1) // max_results
                    ),
                )
            else:
                pages_this = 0

            envelope = self._save_envelope(
                query=query,
                options={
                    **call_opts,
                    "since_id": since_id,
                    "until_id": current_until_id,
                },
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

    def budget_exhausted_reason(self) -> str | None:
        """Why a daily or monthly spend cap forbids fetching now, else ``None``.

        The check :meth:`run` makes before it calls the X API, public so that a
        caller (the durable search flow) can make it as a step of its own.
        """
        return self.__budget.exhausted_reason()

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
        # the search flow try again on its next tick. The counter resets
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
        try:
            with ThreadPoolExecutor(max_workers=len(queries)) as executor:
                results = list(
                    executor.map(
                        lambda query: self._process_query(query, options),
                        queries,
                    )
                )
        except Exception:
            # A batch failed part-way: the pages X answered before it were
            # billed (saved in an envelope or not), so charge them before the
            # error goes up. ``max``: an integration that reports no pages
            # still charges what was saved.
            self.__budget.record(max(self.__billed_tweets, self.__saved_tweets))
            raise

        total_new = sum(item["new_count"] for item in results)
        # Charge the budget for every tweet ('resource') actually retrieved so
        # the next tick sees the updated spend.
        self.__budget.record(max(self.__billed_tweets, total_new))
        return {
            "total_new_tweets": total_new,
            "results": results,
            "budget_blocked": False,
            "budget": self.__budget.snapshot(),
        }


# Public names of the ledger, for the agent's search tool and the flows.
BudgetLimits = _BudgetLimits
XApiBudget = _XApiBudget


def budget_ledger(
    object_storage: Any,
    datastore_path: str,
    budget_key: str,
    limits: _BudgetLimits,
) -> _XApiBudget:
    """The spend ledger of ``budget_key`` at ``<datastore_path>/_budget/<slug>.json``
    (the file ``XSearchRecentTweetsWorkflow`` keeps), over the blocking object
    storage."""
    return _XApiBudget(
        StorageUtils(object_storage),
        os.path.join(datastore_path, "_budget"),
        budget_key,
        limits,
    )


def _pages(tool: str, max_pages: Any) -> int:
    """A tool's ``max_pages``: a number of pages; "every page" is refused."""
    if max_pages is None:
        raise ValueError(
            f"{tool}: max_pages must be a number of pages; fetching every page "
            "is refused for the agent"
        )
    return int(max_pages)


def _within_budget(
    budget: _XApiBudget,
    run: Callable[[Awaitable[Any]], Any],
    call: Callable[[int, Callable[[dict], None]], Awaitable[dict]],
    *,
    max_pages: int,
    max_results: int,
) -> tuple[dict | None, str | None]:
    """``call(max_pages, on_page)`` under ``budget``: ``(result, None)``, or
    ``(None, reason)`` without calling X when a cap is reached.

    The allowance is reserved first (``_XApiBudget.reserve``, which also
    limits the pages), then settled to the tweets of the pages X answered,
    also when the call fails part-way or its result cannot be saved.
    """
    reservation = budget.reserve(max_pages, max_results)
    if isinstance(reservation, str):
        return None, reservation
    billed = 0

    def count(page: dict) -> None:  # on the loop: only counts
        nonlocal billed
        billed += page_resources(page)

    try:
        return run(call(reservation.max_pages, count)), None
    finally:
        budget.settle(reservation, billed)


def search_with_budget(
    budget: _XApiBudget,
    run: Callable[[Awaitable[Any]], Any],
    x_integration: XIntegration,
    query: str,
    **options: Any,
) -> dict:
    """One ``XIntegration.search_recent_tweets`` call under ``budget``.

    Synchronous (a worker thread). A spent daily or monthly cap returns
    ``{"budget_blocked": True, "budget_reason", "budget"}`` without calling X.
    Otherwise the search fetches ``max_pages`` (default 1; ``None`` is refused),
    at most what the caps leave (``_XApiBudget.reserve``), through ``run``; the
    tweets X returned are recorded, also when the search fails part-way. The
    envelope comes back with the ledger's ``budget`` snapshot and
    ``budget_blocked: False``.
    """
    max_pages = _pages("x_search_recent_tweets", options.pop("max_pages", 1))
    max_results = int(options.get("max_results") or 100)
    envelope, blocked_reason = _within_budget(
        budget,
        run,
        lambda pages, on_page: x_integration.search_recent_tweets(
            query, max_pages=pages, on_page=on_page, **options
        ),
        max_pages=max_pages,
        max_results=max_results,
    )
    if blocked_reason is not None:
        logger.warning(f"x_search_recent_tweets: skipping fetch — {blocked_reason}")
        return {
            "query": query,
            "results": {"data": []},
            "budget_blocked": True,
            "budget_reason": blocked_reason,
            "budget": budget.snapshot(),
        }
    return {**(envelope or {}), "budget_blocked": False, "budget": budget.snapshot()}


def read_with_budget(
    budget: _XApiBudget,
    run: Callable[[Awaitable[Any]], Any],
    read: Callable[..., Awaitable[dict]],
    user_id: str,
    *,
    max_results: int,
    max_pages: int,
) -> dict:
    """One paginated user read of the agent (``XIntegration.get_user_tweets``
    ... ``get_user_following``) under ``budget``, as :func:`search_with_budget`.

    X bills these per resource returned, as a search: each tweet or user
    counts as one in the ledger. X may price a user read at another unit price
    than a tweet; the ledger keeps a single count, converted to USD at the
    ledger's ``cost_per_tweet_usd`` for both. A cached read bills nothing.
    A spent cap returns ``{"data": [], "budget_blocked": True, ...}``.
    """
    name = getattr(read, "__name__", "x_get_user_read")
    pages = _pages(name, max_pages)
    result, blocked_reason = _within_budget(
        budget,
        run,
        lambda n, on_page: read(user_id, max_results, n, on_page=on_page),
        max_pages=pages,
        max_results=max_results,
    )
    if blocked_reason is not None:
        logger.warning(f"{name}: skipping fetch — {blocked_reason}")
        return {
            "data": [],
            "budget_blocked": True,
            "budget_reason": blocked_reason,
            "budget": budget.snapshot(),
        }
    return {**(result or {}), "budget_blocked": False, "budget": budget.snapshot()}
