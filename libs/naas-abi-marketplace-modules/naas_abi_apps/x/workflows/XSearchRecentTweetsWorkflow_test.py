"""Offline tests of the search workflow: spend ledger, since_id cursor,
batched envelopes, and a whole run over a fake X API and object storage."""

import asyncio
import json

import httpx
import pytest
from naas_abi_apps.x.integrations.XIntegration import (
    XIntegration,
    XIntegrationConfiguration,
)
from naas_abi_apps.x.services import SyncService
from naas_abi_apps.x.workflows.XSearchRecentTweetsWorkflow import (
    BudgetLimits,
    XSearchRecentTweetsWorkflow,
    XSearchRecentTweetsWorkflowConfiguration,
    XSearchRecentTweetsWorkflowParameters,
    _BudgetLimits,
    _XApiBudget,
    budget_ledger,
    search_with_budget,
)
from naas_abi_sdk.integration import IntegrationConnectionError


class _FakeStorage:
    """In-memory stand-in for the object-storage-backed StorageUtils.

    Only the two methods _XApiBudget calls are implemented; keyed by
    ``(dir_path, file_name)`` so the budget ledger round-trips like the real
    JSON object would.
    """

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], dict | list] = {}

    def get_json(self, dir_path: str, file_name: str) -> dict:
        # Matches StorageUtils.get_json: missing file -> {}.
        stored = self.store.get((dir_path, file_name), {})
        return stored if isinstance(stored, dict) else {}

    def save_json(
        self, data: dict | list, dir_path: str, file_name: str, copy: bool = True
    ) -> tuple[str, str]:
        self.store[(dir_path, file_name)] = data
        return dir_path, file_name


def _budget(limits: _BudgetLimits) -> _XApiBudget:
    return _XApiBudget(_FakeStorage(), "x/_budget", "test_filter", limits)


# --------------------------------------------------------------- cap resolution


def test_usd_cap_converts_to_tweet_count():
    limits = _BudgetLimits(
        cost_per_tweet_usd=0.005,
        daily_max_tweets=None,
        daily_max_usd=0.5,
        monthly_max_tweets=None,
        monthly_max_usd=5.0,
    )
    # $0.50 / $0.005 == 100 and $5.00 / $0.005 == 1000, with no float off-by-one.
    assert limits.daily_tweet_cap == 100
    assert limits.monthly_tweet_cap == 1000


def test_more_restrictive_cap_wins_when_both_set():
    limits = _BudgetLimits(
        cost_per_tweet_usd=0.005,
        daily_max_tweets=50,  # 50 tweets
        daily_max_usd=0.5,  # == 100 tweets
        monthly_max_tweets=None,
        monthly_max_usd=None,
    )
    assert limits.daily_tweet_cap == 50


def test_no_cap_when_both_inputs_none():
    limits = _BudgetLimits(0.005, None, None, None, None)
    assert limits.daily_tweet_cap is None
    assert limits.monthly_tweet_cap is None


# ------------------------------------------------------------- ledger behaviour


def test_record_accumulates_and_blocks_when_daily_cap_reached():
    limits = _BudgetLimits(
        cost_per_tweet_usd=0.005,
        daily_max_tweets=100,
        daily_max_usd=None,
        monthly_max_tweets=None,
        monthly_max_usd=None,
    )
    budget = _budget(limits)

    assert budget.exhausted_reason() is None
    budget.record(80)
    assert budget.usage()[0] == 80
    assert budget.exhausted_reason() is None  # still under the cap

    budget.record(30)  # 110 >= 100
    assert budget.usage()[0] == 110
    reason = budget.exhausted_reason()
    assert reason is not None and "daily" in reason


def test_monthly_cap_blocks_independently_of_daily():
    limits = _BudgetLimits(
        cost_per_tweet_usd=0.005,
        daily_max_tweets=None,  # no daily cap
        daily_max_usd=None,
        monthly_max_tweets=10,
        monthly_max_usd=None,
    )
    budget = _budget(limits)
    budget.record(10)
    reason = budget.exhausted_reason()
    assert reason is not None and "monthly" in reason


def test_record_zero_or_negative_is_noop():
    budget = _budget(_BudgetLimits(0.005, 100, None, None, None))
    budget.record(0)
    budget.record(-5)
    assert budget.usage() == (0, 0)


def test_filters_track_separate_ledgers():
    # Same backing storage, different budget keys -> independent counters.
    storage = _FakeStorage()
    limits = _BudgetLimits(0.005, 10, None, None, None)
    a = _XApiBudget(storage, "x/_budget", "filter_a", limits)
    b = _XApiBudget(storage, "x/_budget", "filter_b", limits)

    a.record(10)
    assert a.exhausted_reason() is not None  # filter_a is capped …
    assert b.exhausted_reason() is None  # … but filter_b is untouched
    assert b.usage() == (0, 0)


def test_batch_max_pages_from_thresholds():
    from naas_abi_apps.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
    )

    assert XSearchRecentTweetsWorkflow._batch_max_pages(10, 1000, 100) == 10
    assert XSearchRecentTweetsWorkflow._batch_max_pages(20, 1000, 100) == 10
    assert XSearchRecentTweetsWorkflow._batch_max_pages(5, 1000, 100) == 5
    assert XSearchRecentTweetsWorkflow._batch_max_pages(None, 250, 100) == 3
    assert XSearchRecentTweetsWorkflow._batch_max_pages(None, None, 100) is None


class _CursorFakeBase:
    """Duck-typed stand-in exercising the cursor helpers off a fake envelope set.

    Starts with no stored cursor, so the getters take the rebuild path and scan
    ``_iter_envelope_filenames`` / ``_load_envelope`` — the behaviour the
    envelope-scanning implementation had, now only used to seed the cursor.
    """

    from naas_abi_apps.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow as _W,
    )

    _CURSOR_VERSION = _W._CURSOR_VERSION
    _envelope_newest_id = staticmethod(_W._envelope_newest_id)
    _envelope_oldest_id = staticmethod(_W._envelope_oldest_id)
    _cursor_from_envelope = staticmethod(_W._cursor_from_envelope)
    _as_dict = staticmethod(_W._as_dict)
    _rebuild_cursor = _W._rebuild_cursor
    _cursor = _W._cursor

    # Envelope basenames the fake exposes, newest first — set per subclass.
    filenames: list[str] = []

    def __init__(self):
        self.saved: dict | None = None
        self.scans = 0

    def _load_cursor(self, query: str):
        return self.saved

    def _save_cursor(self, query: str, cursor: dict) -> None:
        self.saved = cursor

    def _iter_envelope_filenames(self, query: str):
        self.scans += 1
        return self.filenames


def test_get_since_id_takes_max_across_batch_files():
    """Later batch files can hold older pages — since_id must be the max id."""
    from naas_abi_apps.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
    )

    class _Fake(_CursorFakeBase):
        filenames = ["b_later.json", "a_earlier.json"]

        def _load_envelope(self, query: str, filename: str):
            return {
                "a_earlier.json": {
                    "batch": {"newest_id": "200", "oldest_id": "150", "has_more": True}
                },
                "b_later.json": {
                    "batch": {"newest_id": "149", "oldest_id": "100", "has_more": False}
                },
            }[filename]

    fake = _Fake()
    assert XSearchRecentTweetsWorkflow.get_since_id(fake, "q") == "200"  # type: ignore[arg-type]
    # Latest file has has_more=False → no until_id resume.
    assert XSearchRecentTweetsWorkflow.get_resume_until_id(fake, "q") is None  # type: ignore[arg-type]

    class _Incomplete(_CursorFakeBase):
        filenames = ["latest.json"]

        def _load_envelope(self, query: str, filename: str):
            return {
                "batch": {"newest_id": "200", "oldest_id": "150", "has_more": True},
                "options": {"since_id": "50"},
            }

    inc = _Incomplete()
    assert XSearchRecentTweetsWorkflow.get_resume_until_id(inc, "q") == "150"  # type: ignore[arg-type]
    assert XSearchRecentTweetsWorkflow.get_resume_since_id(inc, "q") == "50"  # type: ignore[arg-type]


def test_cursor_is_built_once_then_reused_without_rescanning():
    """The whole point of the cursor: one scan, then O(1) reads."""
    from naas_abi_apps.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
    )

    class _Fake(_CursorFakeBase):
        filenames = ["latest.json", "older.json"]

        def _load_envelope(self, query: str, filename: str):
            return {
                "latest.json": {
                    "batch": {"newest_id": "300", "oldest_id": "250", "has_more": True},
                    "options": {"since_id": "100"},
                },
                "older.json": {
                    "batch": {"newest_id": "240", "oldest_id": "200", "has_more": False}
                },
            }[filename]

    fake = _Fake()
    assert XSearchRecentTweetsWorkflow.get_since_id(fake, "q") == "300"  # type: ignore[arg-type]
    assert fake.scans == 1
    # Every later read is served from the stored cursor — no second scan.
    assert XSearchRecentTweetsWorkflow.get_since_id(fake, "q") == "300"  # type: ignore[arg-type]
    assert XSearchRecentTweetsWorkflow.get_resume_until_id(fake, "q") == "250"  # type: ignore[arg-type]
    assert XSearchRecentTweetsWorkflow.get_resume_since_id(fake, "q") == "100"  # type: ignore[arg-type]
    assert fake.scans == 1


def test_advance_cursor_keeps_max_newest_id_but_follows_latest_envelope():
    """A resume walk saves *older* pages — they must not drag since_id back."""
    from naas_abi_apps.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
    )

    class _Fake(_CursorFakeBase):
        filenames: list[str] = []
        _advance_cursor = XSearchRecentTweetsWorkflow._advance_cursor

    fake = _Fake()
    # Phase B: newest tweets.
    XSearchRecentTweetsWorkflow._advance_cursor(  # type: ignore[arg-type]
        fake,
        "q",
        {"batch": {"newest_id": "500", "oldest_id": "450", "has_more": True}},
        "b.json",
    )
    assert XSearchRecentTweetsWorkflow.get_since_id(fake, "q") == "500"  # type: ignore[arg-type]

    # Phase A: an older resume batch, complete this time.
    XSearchRecentTweetsWorkflow._advance_cursor(  # type: ignore[arg-type]
        fake,
        "q",
        {
            "batch": {"newest_id": "449", "oldest_id": "400", "has_more": False},
            "options": {"since_id": "100"},
        },
        "a.json",
    )
    assert XSearchRecentTweetsWorkflow.get_since_id(fake, "q") == "500"  # type: ignore[arg-type]
    # …and resume state now tracks that last-written envelope.
    assert XSearchRecentTweetsWorkflow.get_resume_until_id(fake, "q") is None  # type: ignore[arg-type]
    assert fake.saved["latest"]["filename"] == "a.json"


def test_fetch_and_save_batches_first_page_has_no_until_id():
    """Page-per-page walk: first envelope is since_id-only; later pages add until_id.

    Matches the contract in XSearchRecentTweetsWorkflow: a fresh since_id window
    starts without until_id; only subsequent batches set
    ``until_id=<oldest id of the previous batch>``.
    """
    from naas_abi_apps.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
    )

    saved: list[dict] = []
    call_log: list[dict] = []

    class _FakeIntegration:
        async def search_recent_tweets(self, query, persist_envelope=False, **opts):
            call_log.append(dict(opts))
            # Two pages worth of results; first call returns has_more.
            if opts.get("until_id") is None:
                return {
                    "results": {
                        "data": [{"id": "300"}, {"id": "200"}],
                        "meta": {
                            "newest_id": "300",
                            "oldest_id": "200",
                            "has_more": True,
                            "result_count": 2,
                        },
                    }
                }
            return {
                "results": {
                    "data": [{"id": "150"}, {"id": "100"}],
                    "meta": {
                        "newest_id": "150",
                        "oldest_id": "100",
                        "has_more": False,
                        "result_count": 2,
                    },
                }
            }

    class _Fake:
        _WORKFLOW_ONLY_OPTION_KEYS = (
            XSearchRecentTweetsWorkflow._WORKFLOW_ONLY_OPTION_KEYS
        )
        _as_dict = staticmethod(XSearchRecentTweetsWorkflow._as_dict)
        _batch_max_pages = staticmethod(XSearchRecentTweetsWorkflow._batch_max_pages)

        def __init__(self) -> None:
            self.__configuration = type(
                "Cfg",
                (),
                {
                    "x_integration": _FakeIntegration(),
                    "datastore_path": "x",
                    "run": staticmethod(asyncio.run),
                },
            )()
            # Bind private name the method reads via name mangling workaround:
            # call unbound method with explicit self that has the attr.
            object.__setattr__(
                self,
                "_XSearchRecentTweetsWorkflow__configuration",
                self.__configuration,
            )

        def _save_envelope(self, **kwargs):
            saved.append(kwargs)
            return {
                "file_path": f"x/{len(saved)}.json",
                "options": {
                    k: v for k, v in kwargs["options"].items() if v is not None
                },
            }

        def _query_prefix(self, query: str) -> str:
            return f"x/search_recent_tweets/{query}"

    fake = _Fake()
    file_paths, tweets, newest, pages_used = (
        XSearchRecentTweetsWorkflow._fetch_and_save_batches(
            fake,  # type: ignore[arg-type]
            "q",
            base_options={"max_results": 100, "sort_order": "recency"},
            since_id="50",
            until_id=None,
            start_time=None,
            overall_max_pages=2,
            save_every_pages=1,
            save_every_tweets=None,
        )
    )

    assert len(saved) == 2
    assert len(call_log) == 2
    assert pages_used == 2
    # First API call / envelope: since_id only.
    assert call_log[0].get("since_id") == "50"
    assert "until_id" not in call_log[0]
    assert saved[0]["options"].get("since_id") == "50"
    assert saved[0]["options"].get("until_id") is None
    # Second page: same since_id + until_id = oldest of first batch.
    assert call_log[1].get("since_id") == "50"
    assert call_log[1].get("until_id") == "200"
    assert saved[1]["options"].get("until_id") == "200"
    assert newest == "300"
    assert [t["id"] for t in tweets] == ["300", "200", "150", "100"]
    assert file_paths == ["x/1.json", "x/2.json"]


def test_process_query_fetches_recents_before_older_resume():
    """Capped max_pages must not spend the whole budget on until_id resume.

    If an incomplete older walk is pending, the first request of the tick must
    still be the fresh since_id walk (no until_id) so we get recent tweets.
    """
    from naas_abi_apps.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
    )

    call_log: list[dict] = []

    class _FakeIntegration:
        async def search_recent_tweets(self, query, persist_envelope=False, **opts):
            call_log.append(dict(opts))
            # Recents walk (no until_id): one page, no more.
            if opts.get("until_id") is None:
                return {
                    "results": {
                        "data": [{"id": "500"}],
                        "meta": {
                            "newest_id": "500",
                            "oldest_id": "500",
                            "has_more": False,
                            "result_count": 1,
                        },
                    }
                }
            # Older resume would return older ids — must not be the first call.
            return {
                "results": {
                    "data": [{"id": "100"}],
                    "meta": {
                        "newest_id": "100",
                        "oldest_id": "90",
                        "has_more": False,
                        "result_count": 1,
                    },
                }
            }

    class _Fake:
        _WORKFLOW_ONLY_OPTION_KEYS = (
            XSearchRecentTweetsWorkflow._WORKFLOW_ONLY_OPTION_KEYS
        )
        _as_dict = staticmethod(XSearchRecentTweetsWorkflow._as_dict)
        _batch_max_pages = staticmethod(XSearchRecentTweetsWorkflow._batch_max_pages)
        _envelope_newest_id = staticmethod(
            XSearchRecentTweetsWorkflow._envelope_newest_id
        )
        _envelope_oldest_id = staticmethod(
            XSearchRecentTweetsWorkflow._envelope_oldest_id
        )

        def __init__(self) -> None:
            cfg = type(
                "Cfg",
                (),
                {
                    "x_integration": _FakeIntegration(),
                    "datastore_path": "x",
                    "run": staticmethod(asyncio.run),
                    "save_every_pages": 1,
                    "save_every_tweets": None,
                },
            )()
            object.__setattr__(self, "_XSearchRecentTweetsWorkflow__configuration", cfg)
            object.__setattr__(
                self,
                "_XSearchRecentTweetsWorkflow__storage_utils",
                type("SU", (), {})(),
            )

        def get_since_id(self, query: str) -> str | None:
            return "400"

        def get_resume_until_id(self, query: str) -> str | None:
            return "150"  # incomplete older walk pending

        def get_resume_since_id(self, query: str) -> str | None:
            return "50"

        def _resolve_save_thresholds(self, options: dict):
            return 1, None

        def _save_envelope(self, **kwargs):
            return {
                "file_path": f"x/{kwargs['options'].get('until_id') or 'recent'}.json"
            }

        def _fetch_and_save_batches(self, *args, **kwargs):
            return XSearchRecentTweetsWorkflow._fetch_and_save_batches(
                self, *args, **kwargs
            )

    fake = _Fake()
    result = XSearchRecentTweetsWorkflow._process_query(
        fake,  # type: ignore[arg-type]
        "q",
        {"max_pages": 1, "max_results": 100},
    )

    assert call_log, "expected at least one X API call"
    # First request must be the recents walk — no until_id.
    assert "until_id" not in call_log[0]
    assert call_log[0].get("since_id") == "400"
    # With max_pages=1 spent on recents, older resume must not run.
    assert all("until_id" not in c for c in call_log)
    assert result["newest_id"] == "500"
    assert result["new_count"] == 1


# ------------------------------------------------- whole runs, offline X API


class _ListedStorage:
    """``MemoryStorage`` with ``list_objects`` (async, as the SDK's)."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    async def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.objects[(prefix, key)] = content

    async def get_object(self, prefix: str, key: str) -> bytes:
        return self.objects[(prefix, key)]

    async def list_objects(self, prefix: str = "") -> list[str]:
        return [f"{p}/{k}" for p, k in self.objects if p == prefix]

    def json(self, prefix: str, key: str) -> dict:
        return json.loads(self.objects[(prefix, key)])


def _page(ids: list[str], next_token: str | None = None) -> dict:
    if not ids:
        return {"meta": {"result_count": 0}}
    meta: dict = {"newest_id": ids[0], "oldest_id": ids[-1], "result_count": len(ids)}
    if next_token:
        meta["next_token"] = next_token
    return {"data": [{"id": i} for i in ids], "meta": meta}


class _SearchApi:
    """``/2/tweets/search/recent``: ``pages[until_id]`` answers, or an error."""

    def __init__(self, pages: dict, fail_on: str | None = None) -> None:
        self.pages = pages
        self.fail_on = fail_on
        self.calls: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        self.calls.append(params)
        until_id = params.get("until_id")
        if until_id is not None and until_id == self.fail_on:
            return httpx.Response(400, json={"title": "Invalid Request"})
        page = self.pages.get(until_id, _page([]))
        since_id = params.get("since_id")
        if since_id is not None:  # as X: only tweets newer than since_id
            ids = [
                t["id"] for t in page.get("data", []) if int(t["id"]) > int(since_id)
            ]
            page = _page(ids, page["meta"].get("next_token") if ids else None)
        return httpx.Response(200, json=page)


def _integration(api: _SearchApi, storage: _ListedStorage) -> XIntegration:
    return XIntegration(
        XIntegrationConfiguration(
            bearer_token="token",
            storage=storage,
            backoff=(),
            transport=httpx.MockTransport(api),
        )
    )


def _workflow(
    api: _SearchApi, storage: _ListedStorage, **config
) -> XSearchRecentTweetsWorkflow:
    return XSearchRecentTweetsWorkflow(
        XSearchRecentTweetsWorkflowConfiguration(
            x_integration=_integration(api, storage),
            object_storage=SyncService(storage, asyncio.run),
            run=asyncio.run,
            **config,
        )
    )


def _parameters(
    query: str = "drones lang:en", **options
) -> XSearchRecentTweetsWorkflowParameters:
    return XSearchRecentTweetsWorkflowParameters(
        queries=[query],
        options={
            "max_results": 100,
            "max_pages": None,
            "save_every_pages": 1,
            **options,
        },
    )


def test_run_saves_batches_records_the_spend_and_resumes_from_since_id():
    api = _SearchApi({None: _page(["9", "8"], "next"), "8": _page(["7"])})
    storage = _ListedStorage()
    workflow = _workflow(api, storage, budget_key="drones", daily_max_tweets=100)

    output = workflow.run(_parameters())

    assert output["total_new_tweets"] == 3
    assert output["budget_blocked"] is False
    assert output["budget"]["tweets_today"] == 3
    assert output["budget"]["usd_today"] == 0.015
    # Fresh walk: a start_time, no until_id; the next batch walks older.
    assert "start_time" in api.calls[0] and "until_id" not in api.calls[0]
    assert api.calls[1]["until_id"] == "8"
    paths = output["results"][0]["file_paths"]
    assert paths == workflow.saved_file_paths()
    assert len(paths) == 2
    assert all(p.startswith("x/search_recent_tweets/drones_lang:en/") for p in paths)
    first = storage.json(*paths[0].rsplit("/", 1))
    assert first["batch"] == {
        "pages": 1,
        "tweet_count": 2,
        "has_more": True,
        "newest_id": "9",
        "oldest_id": "8",
    }
    assert set(first) == {
        "query",
        "options",
        "results",
        "started_at",
        "ended_at",
        "file_path",
        "batch",
    }
    ledger = storage.json("x/_budget", "drones.json")
    assert list(ledger["daily"].values()) == [3]
    assert list(ledger["monthly"].values()) == [3]
    assert storage.json("x/_cursors", "drones_lang:en.json")["newest_id"] == "9"

    # The next tick asks only for newer tweets.
    workflow = _workflow(api, storage, budget_key="drones", daily_max_tweets=100)
    assert workflow.run(_parameters())["total_new_tweets"] == 0
    assert api.calls[-1]["since_id"] == "9"
    assert "start_time" not in api.calls[-1]


def test_a_spent_cap_fetches_nothing():
    api = _SearchApi({None: _page(["9", "8", "7"])})
    storage = _ListedStorage()
    caps = {"budget_key": "drones", "daily_max_usd": 0.01}  # 2 tweets at $0.005

    first = _workflow(api, storage, **caps).run(_parameters())
    assert first["total_new_tweets"] == 3  # all-or-nothing: the run that crosses
    calls = len(api.calls)

    workflow = _workflow(api, storage, **caps)
    reason = workflow.budget_exhausted_reason()
    assert reason is not None and "daily X budget reached: 3/2 tweets" in reason
    second = workflow.run(_parameters())
    assert second["budget_blocked"] is True
    assert second["budget_reason"] == reason
    assert second["results"] == []
    assert len(api.calls) == calls


def test_a_failed_batch_records_the_tweets_already_saved():
    api = _SearchApi({None: _page(["9", "8"], "next")}, fail_on="8")
    storage = _ListedStorage()
    workflow = _workflow(api, storage, budget_key="drones")

    with pytest.raises(IntegrationConnectionError):
        workflow.run(_parameters())

    assert len(workflow.saved_file_paths()) == 1
    assert list(storage.json("x/_budget", "drones.json")["daily"].values()) == [2]


def test_each_filter_keeps_its_own_ledger():
    api = _SearchApi({None: _page(["9"])})
    storage = _ListedStorage()

    _workflow(api, storage, budget_key="a", daily_max_tweets=1).run(_parameters("a"))

    blocked = _workflow(api, storage, budget_key="a", daily_max_tweets=1)
    other = _workflow(api, storage, budget_key="b", daily_max_tweets=1)
    assert blocked.budget_exhausted_reason() is not None
    assert other.budget_exhausted_reason() is None


def test_unknown_options_are_refused():
    workflow = _workflow(_SearchApi({}), _ListedStorage())
    with pytest.raises(ValueError, match="since_id"):
        workflow.run(_parameters(since_id="1"))


def test_search_with_budget_records_then_blocks():
    api = _SearchApi({None: _page(["9", "8"])})
    storage = _ListedStorage()
    integration = _integration(api, storage)
    ledger = budget_ledger(
        SyncService(storage, asyncio.run),
        "x",
        "agent",
        BudgetLimits(0.005, 2, None, None, None),
    )

    envelope = search_with_budget(ledger, asyncio.run, integration, "q")
    assert envelope["budget_blocked"] is False
    assert envelope["budget"]["tweets_today"] == 2
    assert envelope["file_path"].startswith("x/search_recent_tweets/q/")

    blocked = search_with_budget(ledger, asyncio.run, integration, "q")
    assert blocked["budget_blocked"] is True
    assert "daily" in blocked["budget_reason"]
    assert len(api.calls) == 1
