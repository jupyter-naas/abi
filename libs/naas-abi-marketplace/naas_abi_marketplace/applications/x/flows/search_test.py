"""``search_recent_tweets``: the steps, their order, the skips, the failures and the replay."""

from __future__ import annotations

import pytest
from naas_abi_core.module.workflows import ChildRunFailed, InvalidWorkflowInput
from naas_abi_marketplace.applications.x.flows import search
from naas_abi_marketplace.applications.x.flows.conftest import (
    FakeFlowContext,
    search_filter,
    x_module,
)
from naas_abi_marketplace.applications.x.flows.fanout import FlowIncomplete
from naas_abi_marketplace.applications.x.flows.models import SearchRecentTweetsInput

PATHS = ["x/search_recent_tweets/news/1.json", "x/search_recent_tweets/news/2.json"]
MAPPED = "map_tweet_envelope"


class Calls:
    """What the stubbed X, graph and app did, and what is made to fail."""

    def __init__(self):
        self.fetch: list[str] = []
        self.budget: list[str] = []
        self.dataset: list[list[str]] = []
        self.publish = 0
        self.mapped: list[str] = []  # envelopes a mapping child was started for
        self.blocked: str | None = None
        self.paths = list(PATHS)
        self.fetch_error: Exception | None = None  # raised after saving paths[0]
        self.fail_dataset = False
        self.fail_publish = False
        self.fail_mapping: set[str] = set()
        self.fail_count = False

    def children(self, workflow, payload):
        if workflow == MAPPED:
            self.mapped.append(payload["path"])
            if payload["path"] in self.fail_mapping:
                raise ChildRunFailed(f"{payload['path']} ended FAILED: boom")
            return {"path": payload["path"], "status": "mapped"}
        if self.fail_count:
            raise ChildRunFailed("count run FAILED")
        return {"query": payload["query"]}


@pytest.fixture
def calls(monkeypatch):
    calls = Calls()

    def fetch(module, config, *args, saved_paths=None, **kwargs):
        calls.fetch.append(config.name)
        if calls.fetch_error is not None:
            saved_paths.append(calls.paths[0])  # one batch was saved before it failed
            raise calls.fetch_error
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
        if calls.fail_publish:
            raise RuntimeError("storage hiccup")
        calls.publish += 1
        return {"queries": 1}

    monkeypatch.setattr(search, "fetch_search_envelopes", fetch)
    monkeypatch.setattr(search, "search_budget_blocked", budget)
    monkeypatch.setattr(search, "sync_x_dataset_paths_batched", dataset)
    monkeypatch.setattr(search, "publish_x_app", publish)
    return calls


def ctx_for(calls, **kwargs):
    return FakeFlowContext(children=calls.children, **kwargs)


def run(module, ctx, name="news"):
    ctx.attach(module)  # the host saved this run as RUNNING before the handler
    return search.run_search_recent_tweets(
        module, ctx, SearchRecentTweetsInput(filter=name)
    )


def running(sequence, filter="news", status="RUNNING"):
    return {
        "run_id": f"search_recent_tweets:{sequence}",
        "job": "search_recent_tweets",
        "status": status,
        "sequence": sequence,
        "payload": {"filter": filter},
    }


def test_the_steps_run_in_order_and_the_mapping_fans_out_over_the_saved_envelopes(
    calls,
):
    module = x_module(search_filter("news", app_publish=True, persist=False))
    ctx = ctx_for(calls)

    out = run(module, ctx)

    assert ctx.stages == ["overlap", "budget", "fetch", "map", "dataset", "publish"]
    children = [(m, w, i) for m, w, i in ctx.called if w == MAPPED]
    assert sorted(i["path"] for _, _, i in children) == PATHS
    assert all(i["persist"] is False for _, _, i in children)
    assert {m for m, _, _ in children} == {ctx.runtime.module_id}
    assert calls.dataset == [PATHS] and calls.publish == 1
    assert (out.envelopes, out.new_tweets, out.mapped) == (2, 7, 2)
    assert out.app == {"queries": 1} and out.dataset == {"batches": 1}
    assert ctx.skipped is None


def test_the_app_is_published_only_when_the_filter_asks_for_it(calls):
    ctx = ctx_for(calls)
    run(x_module(search_filter("news")), ctx)
    assert "publish" not in ctx.stages and calls.publish == 0


def test_a_tick_with_nothing_new_maps_nothing_and_syncs_nothing(calls):
    calls.paths = []
    ctx = ctx_for(calls)
    out = run(x_module(search_filter("news")), ctx)
    assert ctx.stages == ["overlap", "budget", "fetch"]
    assert (out.envelopes, out.mapped, out.dataset) == (0, 0, None)


def test_an_envelope_whose_mapping_run_was_skipped_is_not_synced(calls):
    ctx = FakeFlowContext(
        children=lambda wf, inp: None if inp["path"] == PATHS[0] else {"ok": 1}
    )
    out = run(x_module(search_filter("news")), ctx)
    assert out.mapped == 1 and calls.dataset == [[PATHS[1]]]


def test_a_tick_whose_previous_run_is_still_running_is_skipped_before_any_work(calls):
    ctx = ctx_for(calls, run_id="search_recent_tweets:10")
    module = x_module(search_filter("news"), records=[running(4)])

    assert run(module, ctx) is None

    assert "search_recent_tweets:4" in ctx.skipped
    assert calls.fetch == [] and calls.budget == [] and ctx.stages == ["overlap"]


def test_filters_run_independently(calls):
    ctx = ctx_for(calls, run_id="search_recent_tweets:10")
    module = x_module(
        search_filter("news"), search_filter("sports"), records=[running(4)]
    )

    out = run(module, ctx, "sports")

    assert out is not None and ctx.skipped is None and calls.fetch == ["sports"]


def test_a_spent_budget_skips_the_run_without_calling_x(calls):
    calls.blocked = "daily X budget reached: 4000/4000 tweets"
    ctx = ctx_for(calls)
    assert run(x_module(search_filter("news")), ctx) is None
    assert ctx.skipped == calls.blocked and calls.fetch == []


def test_a_failed_count_follow_up_does_not_fail_the_search(calls):
    calls.fail_count = True
    ctx = ctx_for(calls)
    out = run(x_module(search_filter("news", count_recent_tweets=True)), ctx)
    assert out.counts_followed is False and out.mapped == 2
    assert "count follow-up failed" in ctx.logs[0]
    assert calls.dataset == [PATHS]  # the chain went on


def test_the_count_is_followed_for_the_filters_query(calls):
    ctx = ctx_for(calls)
    out = run(x_module(search_filter("news", count_recent_tweets=True)), ctx)
    assert [(m, w, i) for m, w, i in ctx.called if w == "count_recent_tweets"] == [
        (ctx.runtime.module_id, "count_recent_tweets", {"query": "news lang:en"})
    ]
    assert out.counts_followed is True


# --- a stage that fails does not stop the ones that can still run ------------------


def test_envelopes_saved_by_a_fetch_that_fails_part_way_are_mapped_then_the_run_fails(
    calls,
):
    calls.fetch_error = RuntimeError("429 Too Many Requests")
    ctx = ctx_for(calls)
    module = x_module(search_filter("news", app_publish=True))

    with pytest.raises(FlowIncomplete) as failure:
        run(module, ctx)

    # the batch saved before the failure was mapped, synced and published...
    assert calls.mapped == [PATHS[0]]
    assert calls.dataset == [[PATHS[0]]] and calls.publish == 1
    # ...and the run still says it failed, and what it did
    message = str(failure.value)
    assert "saved 1 envelope(s), mapped 1" in message
    assert "the fetch failed after saving 1 envelope(s)" in message
    assert "429 Too Many Requests" in message


def test_a_retry_of_a_run_whose_fetch_failed_does_not_call_x_again(calls):
    calls.fetch_error = RuntimeError("429")
    module, journal = x_module(search_filter("news")), {}
    with pytest.raises(FlowIncomplete):
        run(module, ctx_for(calls, journal=journal))
    retry = ctx_for(calls, journal=journal)
    with pytest.raises(FlowIncomplete):
        run(module, retry)
    assert calls.fetch == ["news"] and calls.mapped == [
        PATHS[0]
    ]  # nothing started again
    assert retry.ran == []


def test_one_failing_mapping_run_does_not_stop_the_others_dataset_sync_and_publish(
    calls,
):
    calls.fail_mapping = {PATHS[0]}
    ctx = ctx_for(calls)
    module = x_module(search_filter("news", app_publish=True, count_recent_tweets=True))

    with pytest.raises(FlowIncomplete) as failure:
        run(module, ctx)

    assert sorted(calls.mapped) == PATHS  # every envelope got its run
    assert calls.dataset == [[PATHS[1]]] and calls.publish == 1  # the good one went on
    assert any(w == "count_recent_tweets" for _, w, _ in ctx.called)
    message = str(failure.value)
    assert "mapping failed for 1 of 2 envelope(s)" in message and PATHS[0] in message
    assert "saved 2 envelope(s), mapped 1" in message


def test_the_retry_of_a_run_with_a_failed_mapping_restarts_only_that_one(calls):
    calls.fail_mapping = {PATHS[0]}
    module, journal = x_module(search_filter("news")), {}
    with pytest.raises(FlowIncomplete):
        run(module, ctx_for(calls, journal=journal))
    calls.mapped.clear()

    calls.fail_mapping = set()  # the envelope maps now
    out = run(module, ctx_for(calls, journal=journal))

    assert calls.mapped == [PATHS[0]]  # not the one that had worked
    assert out.mapped == 2 and calls.fetch == ["news"]
    assert calls.dataset[-1] == PATHS  # the set grew: it is synced again


def test_a_failed_dataset_sync_does_not_stop_the_publish_and_the_error_says_what_worked(
    calls,
):
    calls.fail_dataset = True
    ctx = ctx_for(calls)
    with pytest.raises(FlowIncomplete) as failure:
        run(x_module(search_filter("news", app_publish=True)), ctx)
    assert calls.publish == 1
    message = str(failure.value)
    assert "saved 2 envelope(s), mapped 2" in message
    assert "the dataset sync failed: dataset is down" in message


def test_a_retry_after_a_failed_dataset_sync_runs_only_that_step(calls):
    calls.fail_dataset = True
    module, journal = x_module(search_filter("news")), {}
    with pytest.raises(FlowIncomplete):
        run(module, ctx_for(calls, journal=journal))
    calls.fail_dataset = False
    retry = ctx_for(calls, journal=journal)

    out = run(module, retry)

    assert calls.fetch == ["news"]  # not fetched again
    assert retry.ran == ["dataset[2]"] and retry.called == []  # no new child
    assert out.mapped == 2 and calls.dataset == [PATHS]


def test_a_failed_app_publish_is_logged_not_fatal(calls):
    calls.fail_publish = True
    ctx = ctx_for(calls)
    out = run(x_module(search_filter("news", app_publish=True)), ctx)
    assert out.app == {"failed": True, "error": "storage hiccup"}
    assert out.mapped == 2 and "app publish failed" in ctx.logs[0]


def test_a_retry_does_not_skip_itself_when_an_earlier_run_is_running_now(calls):
    calls.fail_dataset = True
    module, journal = x_module(search_filter("news")), {}
    with pytest.raises(FlowIncomplete):
        run(module, ctx_for(calls, journal=journal))

    calls.fail_dataset = False
    module._job_host()[0].documents.records.append(
        running(3)
    )  # an older run, active now
    retry = ctx_for(calls, journal=journal)
    assert run(module, retry) is not None and retry.skipped is None


def test_an_unknown_filter_fails_the_run_without_a_retry(calls):
    with pytest.raises(InvalidWorkflowInput, match="nope"):
        run(x_module(search_filter("news")), ctx_for(calls), "nope")
    assert calls.fetch == []
