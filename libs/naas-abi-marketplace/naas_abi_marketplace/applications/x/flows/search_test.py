"""``search_recent_tweets``: the steps, their order, the skips and the replay."""

from __future__ import annotations

import pytest
from naas_abi_core.module.workflows import ChildRunFailed, InvalidWorkflowInput
from naas_abi_marketplace.applications.x.flows import search
from naas_abi_marketplace.applications.x.flows.conftest import (
    FakeFlowContext,
    search_filter,
    x_module,
)
from naas_abi_marketplace.applications.x.flows.models import SearchRecentTweetsInput

PATHS = ["x/search_recent_tweets/news/1.json", "x/search_recent_tweets/news/2.json"]


class Calls:
    """What the stubbed X, graph and app did."""

    def __init__(self):
        self.fetch: list[str] = []
        self.budget: list[str] = []
        self.dataset: list[list[str]] = []
        self.publish = 0
        self.blocked: str | None = None
        self.paths = list(PATHS)
        self.fail_dataset = False


@pytest.fixture
def calls(monkeypatch):
    calls = Calls()

    def fetch(module, config, *args, **kwargs):
        calls.fetch.append(config.name)
        return {
            "file_paths": list(calls.paths),
            "total_new_tweets": 7,
            "budget_blocked": False,
            "budget_reason": None,
        }

    def budget(module, config):
        calls.budget.append(config.name)
        return calls.blocked

    def dataset(module, paths, **kwargs):
        if calls.fail_dataset:
            raise RuntimeError("dataset is down")
        calls.dataset.append(list(paths))
        return {"batches": 1}

    def publish(module, **kwargs):
        calls.publish += 1
        return {"queries": 1}

    monkeypatch.setattr(search, "fetch_search_envelopes", fetch)
    monkeypatch.setattr(search, "search_budget_blocked", budget)
    monkeypatch.setattr(search, "sync_x_dataset_paths_batched", dataset)
    monkeypatch.setattr(search, "publish_x_app", publish)
    return calls


def run(module, ctx, name="news"):
    return search.run_search_recent_tweets(
        module, ctx, SearchRecentTweetsInput(filter=name)
    )


def test_the_steps_run_in_order_and_the_mapping_fans_out_over_the_saved_envelopes(
    calls,
):
    module = x_module(search_filter("news", app_publish=True, persist=False))
    ctx = FakeFlowContext(
        children=lambda wf, inp: {"path": inp["path"], "status": "mapped"}
    )

    out = run(module, ctx)

    assert ctx.ran == ["overlap", "budget", "fetch", "map", "dataset", "publish"]
    module_id, workflow, inputs = ctx.fanned[0]
    assert (module_id, workflow) == (ctx.runtime.module_id, "map_tweet_envelope")
    assert inputs == [{"path": p, "persist": False} for p in PATHS]
    assert calls.dataset == [PATHS] and calls.publish == 1
    assert (out.envelopes, out.new_tweets, out.mapped) == (2, 7, 2)
    assert out.app == {"queries": 1} and out.dataset == {"batches": 1}
    assert ctx.skipped is None


def test_the_app_is_published_only_when_the_filter_asks_for_it(calls):
    ctx = FakeFlowContext()
    run(x_module(search_filter("news")), ctx)
    assert "publish" not in ctx.ran and calls.publish == 0


def test_a_tick_with_nothing_new_maps_nothing_and_syncs_nothing(calls):
    calls.paths = []
    ctx = FakeFlowContext()
    out = run(x_module(search_filter("news")), ctx)
    assert ctx.ran == ["overlap", "budget", "fetch"]
    assert (out.envelopes, out.mapped, out.dataset) == (0, 0, None)


def test_an_envelope_whose_mapping_run_was_skipped_is_not_synced(calls):
    ctx = FakeFlowContext(
        children=lambda wf, inp: None if inp["path"] == PATHS[0] else {"ok": 1}
    )
    out = run(x_module(search_filter("news")), ctx)
    assert out.mapped == 1 and calls.dataset == [[PATHS[1]]]


def test_a_tick_whose_previous_run_is_still_running_is_skipped_before_any_work(calls):
    running = {
        "run_id": "search_recent_tweets:4",
        "job": "search_recent_tweets",
        "status": "RUNNING",
        "sequence": 4,
        "payload": {"filter": "news"},
    }
    ctx = FakeFlowContext(run_id="search_recent_tweets:10")

    assert run(x_module(search_filter("news"), records=[running]), ctx) is None

    assert "search_recent_tweets:4" in ctx.skipped
    assert calls.fetch == [] and calls.budget == [] and ctx.ran == ["overlap"]


def test_filters_run_independently(calls):
    running = {
        "run_id": "search_recent_tweets:4",
        "job": "search_recent_tweets",
        "status": "RUNNING",
        "sequence": 4,
        "payload": {"filter": "news"},
    }
    ctx = FakeFlowContext(run_id="search_recent_tweets:10")
    module = x_module(search_filter("news"), search_filter("sports"), records=[running])

    out = run(module, ctx, "sports")

    assert out is not None and ctx.skipped is None and calls.fetch == ["sports"]


def test_a_spent_budget_skips_the_run_without_calling_x(calls):
    calls.blocked = "daily X budget reached: 4000/4000 tweets"
    ctx = FakeFlowContext()
    assert run(x_module(search_filter("news")), ctx) is None
    assert ctx.skipped == calls.blocked and calls.fetch == []


def test_a_failed_count_follow_up_does_not_fail_the_search(calls):
    def children(workflow, payload):
        if workflow == "count_recent_tweets":
            raise ChildRunFailed("count run FAILED")
        return {"ok": True}

    ctx = FakeFlowContext(children=children)
    out = run(x_module(search_filter("news", count_recent_tweets=True)), ctx)
    assert out.counts_followed is False and out.mapped == 2
    assert "count follow-up failed" in ctx.logs[0]
    assert calls.dataset == [PATHS]  # the chain went on


def test_the_count_is_followed_for_the_filters_query(calls):
    ctx = FakeFlowContext()
    out = run(x_module(search_filter("news", count_recent_tweets=True)), ctx)
    assert ctx.called == [
        (ctx.runtime.module_id, "count_recent_tweets", {"query": "news lang:en"})
    ]
    assert out.counts_followed is True


def test_a_retry_after_the_fetch_does_not_call_x_again_nor_start_new_children(calls):
    module = x_module(search_filter("news"))
    journal: dict = {}
    calls.fail_dataset = True
    with pytest.raises(RuntimeError, match="dataset is down"):
        run(module, FakeFlowContext(journal=journal))
    assert calls.fetch == ["news"]

    calls.fail_dataset = False  # the retry: same run, same journal
    retry = FakeFlowContext(journal=journal)
    out = run(module, retry)

    assert calls.fetch == ["news"]  # not fetched again
    assert retry.ran == ["dataset"] and retry.fanned == []  # only what had not run
    assert out.mapped == 2 and calls.dataset == [PATHS]


def test_a_retry_does_not_skip_itself_when_an_earlier_run_is_running_now(calls):
    module = x_module(search_filter("news"))
    journal: dict = {}
    calls.fail_dataset = True
    with pytest.raises(RuntimeError):
        run(module, FakeFlowContext(journal=journal))

    calls.fail_dataset = False
    earlier = {
        "run_id": "search_recent_tweets:3",
        "job": "search_recent_tweets",
        "status": "RUNNING",
        "sequence": 3,
        "payload": {"filter": "news"},
    }
    module._job_host()[0].documents.records.append(earlier)
    retry = FakeFlowContext(journal=journal)
    assert run(module, retry) is not None and retry.skipped is None


def test_an_unknown_filter_fails_the_run_without_a_retry(calls):
    with pytest.raises(InvalidWorkflowInput, match="nope"):
        run(x_module(search_filter("news")), FakeFlowContext(), "nope")
    assert calls.fetch == []
