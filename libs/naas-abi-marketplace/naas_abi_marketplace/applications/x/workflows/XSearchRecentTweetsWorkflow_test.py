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


def test_get_since_id_takes_max_across_batch_files():
    """Later batch files can hold older pages — since_id must be the max id."""
    from naas_abi_marketplace.applications.x.workflows.XSearchRecentTweetsWorkflow import (
        XSearchRecentTweetsWorkflow,
    )

    class _Fake:
        _envelope_newest_id = staticmethod(XSearchRecentTweetsWorkflow._envelope_newest_id)
        _envelope_oldest_id = staticmethod(XSearchRecentTweetsWorkflow._envelope_oldest_id)
        _as_dict = staticmethod(XSearchRecentTweetsWorkflow._as_dict)

        def _iter_envelope_filenames(self, query: str):
            return ["b_later.json", "a_earlier.json"]

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

    class _Incomplete:
        _envelope_newest_id = staticmethod(XSearchRecentTweetsWorkflow._envelope_newest_id)
        _envelope_oldest_id = staticmethod(XSearchRecentTweetsWorkflow._envelope_oldest_id)
        _as_dict = staticmethod(XSearchRecentTweetsWorkflow._as_dict)

        def _iter_envelope_filenames(self, query: str):
            return ["latest.json"]

        def _load_envelope(self, query: str, filename: str):
            return {
                "batch": {"newest_id": "200", "oldest_id": "150", "has_more": True},
                "options": {"since_id": "50"},
            }

    inc = _Incomplete()
    assert XSearchRecentTweetsWorkflow.get_resume_until_id(inc, "q") == "150"  # type: ignore[arg-type]
    assert XSearchRecentTweetsWorkflow.get_resume_since_id(inc, "q") == "50"  # type: ignore[arg-type]
