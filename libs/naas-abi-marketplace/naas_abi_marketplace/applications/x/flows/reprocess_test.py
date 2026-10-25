"""``reprocess_tweet_envelopes``: re-maps what is missing, and is a no-op after."""

from __future__ import annotations

import json

import pytest
from naas_abi_core.module.workflows import ChildRunFailed
from naas_abi_marketplace.applications.x.flows import reprocess
from naas_abi_marketplace.applications.x.flows.conftest import FakeFlowContext, x_module
from naas_abi_marketplace.applications.x.flows.fanout import FlowIncomplete
from naas_abi_marketplace.applications.x.flows.models import (
    ReprocessTweetEnvelopesInput,
)

PREFIX = "x/search_recent_tweets"
ENVELOPES = [f"{PREFIX}/news/2026-10-25T10:0{i}:00_news.json" for i in range(4)]


class World:
    """The envelopes in storage, and which of them the graph and the dataset hold."""

    def __init__(self):
        self.listed = list(ENVELOPES)
        self.in_graph: set[str] = set()
        self.in_dataset: set[str] = set()
        self.synced: list[list[str]] = []
        self.published = 0

    def map_all(self, paths):
        self.in_graph |= set(paths)

    def sync(self, paths):
        self.in_dataset |= {p.lstrip("/") for p in paths}


@pytest.fixture
def world(monkeypatch):
    world = World()
    monkeypatch.setattr(
        reprocess,
        "list_envelope_paths",
        lambda storage, prefix, cutoff=None: (list(world.listed), 0),
    )
    monkeypatch.setattr(reprocess, "mapped_file_paths", lambda *a: set(world.in_graph))
    monkeypatch.setattr(
        reprocess,
        "envelope_paths_in_dataset",
        lambda module, paths: set(world.in_dataset),
    )

    def sync(module, paths, **kwargs):
        world.synced.append(list(paths))
        world.sync(paths)
        return {"batches": 1}

    def publish(module, **kwargs):
        world.published += 1
        return {"queries": 1}

    monkeypatch.setattr(reprocess, "sync_x_dataset_paths_batched", sync)
    monkeypatch.setattr(reprocess, "publish_x_app", publish)
    return world


def run(world, fail=(), records=None, payload=None, **inp):
    """One run; its children map what they are given, as ``map_tweet_envelope`` does."""
    mapped: list[dict] = []

    def children(workflow, payload):
        mapped.append(payload)
        if payload["path"] in fail:
            raise ChildRunFailed(f"{payload['path']} ended FAILED: boom")
        world.map_all([payload["path"]])
        return {"path": payload["path"], "status": "mapped"}

    ctx = FakeFlowContext(
        job="reprocess_tweet_envelopes",
        run_id="reprocess_tweet_envelopes:10",
        children=children,
        payload={"prefix": PREFIX} if payload is None else payload,
    )
    module = x_module(object_storage=object(), triple_store=object(), records=records)
    ctx.attach(module)
    out = reprocess.run_reprocess_tweet_envelopes(
        module, ctx, ReprocessTweetEnvelopesInput(prefix=PREFIX, **inp)
    )
    return out, ctx, mapped


def test_every_envelope_under_the_prefix_is_mapped_then_synced(world):
    out, ctx, mapped = run(world, persist=False)
    assert ctx.stages == ["overlap", "plan", "map", "dataset"]
    assert [m["path"] for m in mapped] == sorted(ENVELOPES)
    assert all(m["persist"] is False for m in mapped)
    assert (out.listed, out.mapped, out.skipped) == (4, 4, 0)
    assert world.synced == [sorted(ENVELOPES)]


def test_a_second_run_is_a_no_op(world):
    run(world)
    out, ctx, mapped = run(world)
    assert mapped == [] and ctx.stages == [
        "overlap",
        "plan",
    ]  # no child, no sync, no publish
    assert (out.listed, out.mapped, out.skipped) == (4, 0, 4)
    assert len(world.synced) == 1


def test_envelopes_the_graph_has_only_need_the_dataset_sync(world):
    world.in_graph = set(ENVELOPES)
    out, ctx, mapped = run(world)
    assert mapped == [] and ctx.stages == ["overlap", "plan", "dataset"]
    assert out.dataset_only == 4 and out.mapped == 0


def test_force_maps_everything_again(world):
    run(world)
    out, _, mapped = run(world, force=True)
    assert len(mapped) == 4 and all(m["force"] for m in mapped)
    assert out.mapped == 4


def test_the_app_is_published_only_when_asked_and_something_was_mapped(world):
    run(world)
    assert world.published == 0
    run(world, app_publish=True)  # nothing left to map
    assert world.published == 0
    world.in_graph.clear()
    world.in_dataset.clear()
    out, _, _ = run(world, app_publish=True)
    assert world.published == 1 and out.app == {"queries": 1}


def test_one_run_takes_at_most_max_envelopes_and_says_so(world):
    out, _, mapped = run(world, max_envelopes=3)
    assert len(mapped) == 3 and out.truncated is True
    out2, _, mapped2 = run(world, max_envelopes=3)  # the rest
    assert len(mapped2) == 1 and out2.truncated is False


def test_an_envelope_skipped_by_its_mapping_run_is_not_synced(world):
    ctx = FakeFlowContext(
        run_id="reprocess_tweet_envelopes:10",
        children=lambda wf, p: None if p["path"] == min(ENVELOPES) else {"ok": 1},
    )
    module = x_module(object_storage=object(), triple_store=object())
    ctx.attach(module)
    out = reprocess.run_reprocess_tweet_envelopes(
        module, ctx, ReprocessTweetEnvelopesInput(prefix=PREFIX)
    )
    assert out.mapped == 3 and min(ENVELOPES) not in world.synced[0]


def test_a_failing_mapping_run_does_not_stop_the_dataset_sync_of_the_others(world):
    bad = min(ENVELOPES)
    with pytest.raises(FlowIncomplete) as failure:
        run(world, fail={bad}, app_publish=True)
    assert world.synced == [sorted(set(ENVELOPES) - {bad})]
    assert world.published == 1
    assert "mapping failed for 1 of 4 envelope(s)" in str(failure.value)
    assert "mapped 3" in str(failure.value)


def test_the_next_run_maps_only_what_failed(world):
    bad = min(ENVELOPES)
    with pytest.raises(FlowIncomplete):
        run(world, fail={bad})
    out, _, mapped = run(world)
    assert [m["path"] for m in mapped] == [bad]
    assert (out.mapped, out.skipped) == (1, 3)


def test_a_sweep_that_is_still_running_makes_the_next_one_skip(world):
    running = {
        "run_id": "reprocess_tweet_envelopes:4",
        "job": "reprocess_tweet_envelopes",
        "status": "RUNNING",
        "sequence": 4,
        "payload": {"prefix": PREFIX},
    }
    out, ctx, mapped = run(world, records=[running])
    assert out is None and mapped == [] and "reprocess_tweet_envelopes:4" in ctx.skipped


def test_a_launch_without_a_prefix_overlaps_a_sweep_of_the_default_prefix(world):
    # a manual launch with `{}` resolves to the default prefix, as the scheduled
    # sweep's payload does: each sees the other
    earlier = {
        "run_id": "reprocess_tweet_envelopes:4",
        "job": "reprocess_tweet_envelopes",
        "status": "RUNNING",
        "sequence": 4,
        "payload": {},
    }
    out, ctx, mapped = run(world, records=[earlier], payload={})
    assert out is None and mapped == [] and "reprocess_tweet_envelopes:4" in ctx.skipped
    other = {**earlier, "payload": {"prefix": "x/other"}}
    out, _, mapped = run(world, records=[other])
    assert out is not None and len(mapped) == 4  # another folder does not block


def test_a_plan_with_long_paths_stays_under_the_step_cap(world):
    slug = "q" * 120
    world.listed = [
        f"{PREFIX}/{slug}/2026-10-25T10:{i // 60:02d}:{i % 60:02d}_{slug}.json"
        for i in range(1500)
    ]
    module = x_module(object_storage=object(), triple_store=object())
    plan = reprocess.plan_reprocess(
        module, ReprocessTweetEnvelopesInput(prefix=PREFIX, max_envelopes=1500)
    )
    assert plan["truncated"] is True
    assert 0 < len(plan["to_map"]) < 1500
    assert len(json.dumps(plan)) < 256 * 1024
