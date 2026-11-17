"""``count_recent_tweets``: fetch, then map; a retry does not fetch again."""

from __future__ import annotations

import asyncio
import threading

import pytest
from naas_abi_apps.x.flows import count
from naas_abi_apps.x.flows.conftest import FakeFlowContext, x_module
from naas_abi_apps.x.flows.models import CountRecentTweetsInput
from naas_abi_apps.x.services import SyncModule


class Calls(list):
    state: dict


@pytest.fixture
def calls(monkeypatch):
    log = Calls()
    state = {"fail_map": False}

    def fetch(module, query):
        log.append(f"fetch {query}")
        return {
            "total_buckets": 24,
            "file_paths": ["x/count/a.json"],
            "partial_file_paths": [{"file_path": "x/count/b.json", "window_end": "t"}],
            "results": [{"big": "per-query detail"}],
        }

    def map_(module, query, output):
        if state["fail_map"]:
            raise RuntimeError("triple store is down")
        log.append(f"map {output['file_paths']}")
        return {"mapped": 1, "partial_mapped": 1}

    monkeypatch.setattr(count, "fetch_counts_for_query", fetch)
    monkeypatch.setattr(count, "map_counts_for_query", map_)
    monkeypatch.setattr(count, "sync_counts_dataset", lambda *a: {"batches": 1})
    log.state = state
    return log


def run(ctx):
    return asyncio.run(
        count.run_count_recent_tweets(
            x_module(), ctx, CountRecentTweetsInput(query="q")
        )
    )


def test_the_count_is_two_steps_fetch_then_map(calls):
    ctx = FakeFlowContext(job="count_recent_tweets")
    out = run(ctx)
    assert ctx.ran == ["fetch", "map"]
    assert ctx.off_loop == {"fetch": True, "map": True}
    assert calls == ["fetch q", "map ['x/count/a.json']"]
    assert (out.buckets, out.mapped, out.partial_mapped) == (24, 1, 1)
    assert out.dataset_sync == {"batches": 1}


def test_the_journaled_fetch_keeps_only_what_the_mapping_needs(calls):
    ctx = FakeFlowContext()
    run(ctx)
    assert set(ctx.journal["fetch"]) == {
        "total_buckets",
        "file_paths",
        "partial_file_paths",
    }


def test_a_retry_after_the_fetch_maps_without_calling_x_again(calls):
    journal: dict = {}
    calls.state["fail_map"] = True
    with pytest.raises(RuntimeError):
        run(FakeFlowContext(journal=journal))
    calls.state["fail_map"] = False
    retry = FakeFlowContext(journal=journal)
    run(retry)
    assert calls.count("fetch q") == 1 and retry.ran == ["map"]


def test_a_step_body_runs_on_the_module_threads(calls, monkeypatch):
    """With the real ``SyncModule``: the step bodies run on its ``x-sync`` pool,
    never on the loop's default executor, where httpx resolves host names."""
    threads: list[str] = []

    def fetch(module, query):
        threads.append(threading.current_thread().name)
        return {"total_buckets": 0, "file_paths": []}

    def map_(module, query, output):
        threads.append(threading.current_thread().name)
        return {"mapped": 0, "partial_mapped": 0}

    monkeypatch.setattr(count, "fetch_counts_for_query", fetch)
    monkeypatch.setattr(count, "map_counts_for_query", map_)
    module = x_module()

    async def scenario():
        module.sync = SyncModule(module, asyncio.get_running_loop())
        try:
            return await count.run_count_recent_tweets(
                module, FakeFlowContext(), CountRecentTweetsInput(query="q")
            )
        finally:
            module.sync.close()

    asyncio.run(scenario())
    assert len(threads) == 2
    assert all(name.startswith("x-sync_") for name in threads), threads
