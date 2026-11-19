"""The synchronous bodies: how they build the domain classes from the module's
``SyncModule``, and the graph probe over the real blocking bridge."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi_apps.common.testing import FakeTripleStore
from naas_abi_apps.x.configuration import XConfiguration, XCountFollowConfiguration
from naas_abi_apps.x.flows import common
from naas_abi_apps.x.flows.conftest import search_filter, x_module
from naas_abi_apps.x.integrations import XIntegration as integration_module
from naas_abi_apps.x.pipelines import XCountRecentTweetsPipeline as count_pipeline
from naas_abi_apps.x.pipelines import XSearchRecentTweetsPipeline as search_pipeline
from naas_abi_apps.x.services import SyncModule
from naas_abi_apps.x.workflows import XCountRecentTweetsWorkflow as count_workflow
from naas_abi_apps.x.workflows import XSearchRecentTweetsWorkflow as search_workflow
from rdflib import Literal, URIRef
from rdflib.namespace import RDF

PATH = "x/search_recent_tweets/news/2026-10-25T10:00:00_news.json"


class Recorder:
    """Stands for a domain class: keeps its configuration and the runs asked of it."""

    instances: list[Recorder]

    def __init__(self, configuration: Any) -> None:
        self.configuration = configuration
        self.runs: list[Any] = []
        type(self).instances.append(self)

    def run(self, parameters: Any) -> Any:
        self.runs.append(parameters)
        return self.output

    output: Any = None


def recorder(output: Any = None, **methods: Any) -> type[Recorder]:
    return type("Recorded", (Recorder,), {"instances": [], "output": output, **methods})


@pytest.fixture
def integration(monkeypatch):
    built: list[Any] = []

    def x_integration_for(module, **overrides):
        built.append(module)
        return "integration"

    monkeypatch.setattr(integration_module, "x_integration_for", x_integration_for)
    return built


def sync_module(**services: Any) -> Any:
    module = x_module(**services)
    module.sync.run = "run"
    return module.sync


def test_the_search_workflow_gets_the_filter_caps_the_bridge_and_the_datastore(
    monkeypatch, integration
):
    workflow = recorder(budget_exhausted_reason=lambda self: "daily cap")
    monkeypatch.setattr(search_workflow, "XSearchRecentTweetsWorkflow", workflow)
    sync = sync_module(object_storage="storage")
    config = search_filter(
        "news", daily_max_usd=20, monthly_max_tweets=900, save_every_pages=3
    )

    assert common.search_budget_blocked(sync, config) == "daily cap"

    cfg = workflow.instances[0].configuration
    assert integration == [sync] and cfg.x_integration == "integration"
    assert (cfg.object_storage, cfg.run, cfg.triple_store) == ("storage", "run", None)
    assert (cfg.datastore_path, cfg.graph_name) == ("x", sync.configuration.graph_name)
    assert cfg.budget_key == "news"
    assert (cfg.daily_max_usd, cfg.monthly_max_tweets) == (20, 900)
    assert (cfg.save_every_pages, cfg.save_every_tweets) == (3, 1000)


def test_the_fetch_runs_the_filter_query_with_its_options(monkeypatch, integration):
    workflow = recorder(
        output={
            "results": [
                {"file_paths": ["a.json", "b.json"]},
                {"file_path": "c.json"},
            ],
            "total_new_tweets": 7,
        }
    )
    monkeypatch.setattr(search_workflow, "XSearchRecentTweetsWorkflow", workflow)
    config = search_filter("news", max_pages=2)

    out = common.fetch_search_envelopes(sync_module(object_storage="s"), config)

    assert out == {
        "file_paths": ["a.json", "b.json", "c.json"],
        "total_new_tweets": 7,
        "budget_blocked": False,
        "budget_reason": None,
    }
    parameters = workflow.instances[0].runs[0]
    assert parameters.queries == ["news lang:en"]
    assert parameters.options == {
        "max_results": 100,
        "max_pages": 2,
        "sort_order": "recency",
        "save_every_pages": 10,
        "save_every_tweets": 1000,
    }


def test_a_fetch_that_fails_part_way_says_what_it_saved(monkeypatch, integration):
    def run(self, parameters):
        raise RuntimeError("429")

    workflow = recorder(run=run, saved_file_paths=lambda self: ["a.json"])
    monkeypatch.setattr(search_workflow, "XSearchRecentTweetsWorkflow", workflow)
    saved: list[str] = []
    with pytest.raises(RuntimeError, match="429"):
        common.fetch_search_envelopes(
            sync_module(object_storage="s"), search_filter("news"), saved_paths=saved
        )
    assert saved == ["a.json"]


def test_the_mapping_runs_the_pipeline_in_file_mode_without_an_integration(
    monkeypatch,
):
    pipeline = recorder()
    monkeypatch.setattr(search_pipeline, "XSearchRecentTweetsPipeline", pipeline)
    sync = sync_module(triple_store="graph", object_storage="storage")

    common.run_search_pipeline_for_file(sync, PATH, persist=False)

    cfg = pipeline.instances[0].configuration
    assert (cfg.triple_store, cfg.object_storage) == ("graph", "storage")
    assert cfg.graph_name == URIRef(sync.configuration.graph_name)
    assert cfg.namespace == sync.configuration.ontology_namespace
    assert (cfg.x_integration, cfg.run) == (None, None)
    parameters = pipeline.instances[0].runs[0]
    assert (parameters.file_path, parameters.persist) == (PATH, False)


def test_a_mapping_into_another_graph_and_persist_by_default(monkeypatch):
    pipeline = recorder()
    monkeypatch.setattr(search_pipeline, "XSearchRecentTweetsPipeline", pipeline)

    common.run_search_pipeline_for_file(
        sync_module(triple_store="g", object_storage="s"), PATH, graph_name="urn:other"
    )

    assert pipeline.instances[0].configuration.graph_name == URIRef("urn:other")
    assert pipeline.instances[0].runs[0].persist is True


def test_the_counts_follow_the_graph_the_search_maps_into(monkeypatch, integration):
    workflow = recorder(output={"total_buckets": 3})
    monkeypatch.setattr(count_workflow, "XCountRecentTweetsWorkflow", workflow)
    sync = sync_module(triple_store="graph", object_storage="storage")

    assert common.fetch_counts_for_query(sync, "q") == {"total_buckets": 3}

    cfg = workflow.instances[0].configuration
    assert integration == [sync] and cfg.x_integration == "integration"
    assert (cfg.triple_store, cfg.object_storage, cfg.run) == (
        "graph",
        "storage",
        "run",
    )
    assert cfg.tweet_graph_name == sync.configuration.graph_name
    assert cfg.namespace == sync.configuration.ontology_namespace
    assert workflow.instances[0].runs[0].queries == ["q"]


def test_the_count_envelopes_map_complete_hours_then_the_partial_one(monkeypatch):
    def run(self, parameters):
        if parameters.file_path == "bad.json":
            raise RuntimeError("unreadable")
        self.runs.append(parameters)

    pipeline = recorder(run=run)
    monkeypatch.setattr(count_pipeline, "XCountRecentTweetsPipeline", pipeline)

    mapped = common.map_counts_for_query(
        sync_module(triple_store="g", object_storage="s"),
        "q",
        {
            "file_paths": ["a.json", "bad.json"],
            "partial_file_paths": [{"file_path": "p.json", "window_end": "t"}],
        },
    )

    assert mapped == {"mapped": 1, "partial_mapped": 1}
    cfg = pipeline.instances[0].configuration
    assert cfg.graph_name == URIRef(common._COUNT_GRAPH_NAME)
    assert cfg.x_integration is None
    partial = pipeline.instances[0].runs[-1]
    assert (partial.file_path, partial.partial, partial.partial_end) == (
        "p.json",
        True,
        "t",
    )


def test_the_graph_probe_goes_through_the_blocking_bridge():
    triple_store = FakeTripleStore()
    configuration = XConfiguration()
    namespace = configuration.ontology_namespace
    graph = triple_store.dataset.graph(URIRef(configuration.graph_name))
    result_set = URIRef("urn:x:rs")
    graph.add((result_set, RDF.type, URIRef(f"{namespace}SearchResultSet")))
    graph.add((result_set, URIRef(f"{namespace}file_path"), Literal(PATH)))
    module = SimpleNamespace(
        configuration=configuration,
        engine=SimpleNamespace(services=SimpleNamespace(triple_store=triple_store)),
    )

    async def probe() -> tuple[bool, bool]:
        sync = SyncModule(module, asyncio.get_running_loop())
        try:
            return (
                await sync.call(common.search_envelope_ingested, sync, PATH),
                await sync.call(common.search_envelope_ingested, sync, "x/o.json"),
            )
        finally:
            sync.close()

    assert asyncio.run(probe()) == (True, False)


def test_a_graph_probe_that_fails_is_not_ingested():
    def query(sparql):
        raise TimeoutError("slow")

    sync = sync_module(triple_store=SimpleNamespace(query=query))
    assert common.search_envelope_ingested(sync, PATH) is False


def test_the_dataset_is_not_probed_while_its_sync_is_off():
    sync = sync_module(dataset="never touched")
    assert common.envelope_paths_in_dataset(sync, [PATH]) == set()
    assert common.search_envelope_in_dataset(sync, PATH) is False


def test_the_dataset_probe_reads_the_envelope_table(monkeypatch):
    from naas_abi_apps.x.x_proxy.dataset import store

    asked: list[Any] = []

    def lookup(dataset, paths):
        asked.append((dataset, list(paths)))
        return {PATH}

    monkeypatch.setattr(store, "envelope_paths_in_dataset", lookup)
    monkeypatch.setattr(store, "envelope_already_ingested", lambda d, p: p == PATH)
    sync = sync_module(dataset="dataset")
    sync.configuration.app.dataset.sync_enabled = True

    assert common.envelope_paths_in_dataset(sync, [PATH]) == {PATH}
    assert common.search_envelope_in_dataset(sync, "/" + PATH) is True
    assert asked == [("dataset", [PATH])]


def test_the_app_is_published_from_the_dataset_for_every_followed_query(monkeypatch):
    from naas_abi_apps.x.x_proxy import hub

    published: list[Any] = []

    class Hub:
        def __init__(self, storage, triple_store, *, namespace):
            published.append((storage, triple_store, namespace))

        def publish(self, queries, *, dataset):
            published.append((queries, dataset))
            return {"queries": len(queries)}

    monkeypatch.setattr(hub, "XAppHubBuilder", Hub)
    module = x_module(
        search_filter("news", count_recent_tweets=True),
        object_storage="storage",
        triple_store="graph",
        dataset="dataset",
    )
    sync = module.sync
    sync.configuration.count_recent_tweets_workflow = [
        XCountFollowConfiguration(name="feed", query="q", enabled=True)
    ]
    sync.configuration.app.dataset.read_enabled = True

    assert common.publish_x_app(sync) == {"queries": 2}
    assert published[0] == ("storage", "graph", sync.configuration.ontology_namespace)
    assert published[1] == (
        [
            {"name": "feed", "query": "q", "label": "feed"},
            {"name": "news", "query": "news lang:en", "label": "news"},
        ],
        "dataset",
    )


def test_the_app_is_not_published_when_disabled_or_without_the_dataset_read(
    monkeypatch,
):
    from naas_abi_apps.x.x_proxy import build

    web: list[Any] = []
    monkeypatch.setattr(
        build,
        "publish_web_export",
        lambda module, *, required: web.append((module, required)) or {"files": 9},
    )
    sync = sync_module(dataset="dataset")
    sync.configuration.app.publish = False
    assert common.publish_x_app(sync)["reason"] == "app.publish=false"
    assert common.publish_x_app(sync, enabled=False)["reason"] == "app_publish=false"
    assert web == []
    # a filter's app_publish wins over app.publish; the snapshots still need the
    # dataset read, the web export does not
    out = common.publish_x_app(sync, enabled=True)
    assert out == {
        "skipped": True,
        "reason": "dataset_read_disabled",
        "web": {"files": 9},
    }
    assert web == [(sync, False)]


def test_the_build_uploads_the_web_export_without_the_dataset_read(monkeypatch):
    """``build_app`` (``app.publish`` true, ``read_enabled`` false: the
    defaults) refreshes the web export even though it builds no snapshot."""
    from naas_abi_apps.x.x_proxy import build

    web: list[Any] = []
    monkeypatch.setattr(
        build,
        "publish_web_export",
        lambda module, *, required: web.append(required) or {"uploaded": 2},
    )
    sync = sync_module(dataset="dataset")
    assert common.publish_x_app(sync)["web"] == {"uploaded": 2}
    assert web == [False]


def test_a_step_result_is_plain_json():
    assert common.jsonable({"at": URIRef("urn:a"), "n": (1, 2)}) == {
        "at": "urn:a",
        "n": [1, 2],
    }
