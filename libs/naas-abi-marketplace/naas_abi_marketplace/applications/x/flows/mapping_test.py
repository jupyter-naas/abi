"""``map_tweet_envelope``: idempotent, whatever state the envelope is in."""

from __future__ import annotations

import pytest
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_marketplace.applications.x.flows import mapping
from naas_abi_marketplace.applications.x.flows.conftest import FakeFlowContext, x_module
from naas_abi_marketplace.applications.x.flows.models import MapTweetEnvelopeInput

PATH = "x/search_recent_tweets/news/2026-10-25T10:00:00_news.json"


class Storage:
    def __init__(self, exists=True, error=None):
        self.exists, self.error, self.probed = exists, error, []

    def get_object_metadata(self, prefix, key):
        self.probed.append((prefix, key))
        if self.error:
            raise self.error
        if not self.exists:
            raise Exceptions.ObjectNotFound(f"{prefix}/{key}")
        return {}


class State:
    """Where the envelope is, and what the pipeline was asked."""

    def __init__(self, *, in_graph=False, in_dataset=False):
        self.in_graph, self.in_dataset = in_graph, in_dataset
        self.mapped: list[dict] = []


@pytest.fixture
def state(monkeypatch):
    state = State()

    def in_graph(module, path, graph_name=None):
        return state.in_graph

    def projected(module, path, graph_name=None):
        return state.in_graph and state.in_dataset

    def pipeline(path, **kwargs):
        kwargs.pop("module")
        state.mapped.append({"path": path, **kwargs})
        state.in_graph = True

    monkeypatch.setattr(mapping, "search_envelope_ingested", in_graph)
    monkeypatch.setattr(mapping, "search_envelope_fully_projected", projected)
    monkeypatch.setattr(mapping, "run_search_pipeline_for_file", pipeline)
    return state


def run(ctx, storage=None, **inp):
    module = x_module(object_storage=storage or Storage())
    return mapping.run_map_tweet_envelope(
        module, ctx, MapTweetEnvelopeInput(path=PATH, **inp)
    )


def test_a_new_envelope_runs_the_pipeline_in_file_path_mode(state):
    ctx = FakeFlowContext()
    out = run(ctx, persist=False)
    assert (out.path, out.status) == (PATH, "mapped")
    assert state.mapped == [{"path": PATH, "persist": False, "graph_name": None}]
    assert ctx.ran == ["pipeline"] and ctx.skipped is None


def test_a_second_run_does_not_map_it_again(state):
    assert run(FakeFlowContext()).status == "mapped"
    state.in_dataset = True  # the caller synced the dataset
    ctx = FakeFlowContext()
    assert run(ctx) is None
    assert ctx.skipped == "already in the graph and the dataset"
    assert len(state.mapped) == 1


def test_an_envelope_the_graph_has_but_the_dataset_lacks_is_not_mapped_again(state):
    state.in_graph = True
    ctx = FakeFlowContext()
    out = run(ctx)
    assert out.status == "dataset_only" and state.mapped == [] and ctx.ran == []


def test_force_maps_it_whatever_the_state(state):
    state.in_graph = state.in_dataset = True
    out = run(FakeFlowContext(), force=True)
    assert out.status == "mapped" and len(state.mapped) == 1


def test_an_envelope_that_is_gone_ends_skipped(state):
    ctx = FakeFlowContext()
    assert run(ctx, storage=Storage(exists=False)) is None
    assert ctx.skipped == "the envelope no longer exists" and state.mapped == []


def test_a_storage_error_does_not_drop_the_envelope(state):
    out = run(FakeFlowContext(), storage=Storage(error=TimeoutError("slow")))
    assert out.status == "mapped"


def test_the_probe_reads_the_envelope_by_prefix_and_key(state):
    storage = Storage()
    run(FakeFlowContext(), storage=storage)
    assert storage.probed == [
        ("x/search_recent_tweets/news", "2026-10-25T10:00:00_news.json")
    ]
