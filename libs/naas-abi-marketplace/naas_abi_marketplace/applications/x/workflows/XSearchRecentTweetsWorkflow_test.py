from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
    _BudgetLimits,
    _XApiBudget,
)


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
    from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
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

    from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
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
    from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
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
    from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
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
    from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
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
    from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
    )

    saved: list[dict] = []
    call_log: list[dict] = []

    class _FakeIntegration:
        def search_recent_tweets(self, query, persist_envelope=False, **opts):
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
                {"x_integration": _FakeIntegration(), "datastore_path": "x"},
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
    from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
    )

    call_log: list[dict] = []

    class _FakeIntegration:
        def search_recent_tweets(self, query, persist_envelope=False, **opts):
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
