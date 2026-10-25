"""The X workflows and jobs on a real broker; requires a local nats-server (>= 2.14).

The real ``ABIModule`` is hosted by the engine's job loader. Run records and journals
live in an in-memory store shared by every loader (as if they shared one Document
Service); the stream, consumers, acks, notices and schedules are real. The X API,
the graph, the dataset and the app are stubbed at the seams ``flows/`` calls.
"""

from __future__ import annotations

import asyncio
import shutil
import socket
import subprocess
import threading
import time
from collections import Counter

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    DiscoveryConfiguration,
    NATSConfiguration,
    NATSJobsConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineJobLoader import EngineJobLoader
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.module.workflows_test import Documents
from naas_abi_marketplace.applications.x.flows import (
    common,
    maintenance,
    mapping,
    reprocess,
    search,
)
from naas_abi_marketplace.applications.x.flows.conftest import (
    real_x_module,
    search_filter,
)
from naas_abi_sdk.jobs import JobRun, runs_collection  # type: ignore[import-not-found]
from naas_abi_sdk.transport import Transport  # type: ignore[import-not-found]
from naas_abi_sdk.workflows import WorkflowRun  # type: ignore[import-not-found]

SECRET = "x-flows-integration-secret-32-bytes"
PROJECT = "xflows"
MODULE_ID = "naas_abi_marketplace.applications.x"

PATHS = [
    f"x/search_recent_tweets/news/2026-10-25T10:0{i}:00_news.json" for i in range(3)
]


@pytest.fixture
def broker(tmp_path):
    binary = shutil.which("nats-server")
    if binary is None:
        pytest.skip("nats-server is not installed")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [
            binary,
            "-a",
            "127.0.0.1",
            "-p",
            str(port),
            "-js",
            "-sd",
            str(tmp_path / "js"),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.01)
        yield f"nats://127.0.0.1:{port}"
    finally:
        process.terminate()
        process.wait(timeout=5)


def wait_for(predicate, timeout=20.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not met in time")
        time.sleep(0.05)


def loader(url, docs):
    return EngineJobLoader(
        NATSConfiguration(
            nats_url=url,
            jwt_secret=SECRET,
            discovery=DiscoveryConfiguration(project=PROJECT),
            jobs=NATSJobsConfiguration(interrupt_grace_seconds=0.2),
        ),
        documents_factory=lambda transport, module_id: docs,
        host_options={
            "fetch_timeout_seconds": 0.2,
            "backoff_base_seconds": 0.2,
            "close_grace_seconds": 0.5,
            "close_cancel_seconds": 2.0,
            "workflow_poll_seconds": 0.5,
        },
    )


def start_host(url, docs, *filters):
    module = real_x_module(*filters, object_storage=object(), triple_store=object())
    module._declare_search_workflows()
    host = loader(url, docs)
    host.start({MODULE_ID: module}, document_available=True)
    return module, host


async def record_of(url, docs, run_id, job, timeout=30):
    transport = Transport(url, issue_service_token("caller", SECRET))
    try:
        run = WorkflowRun(
            JobRun(transport, PROJECT, MODULE_ID, job, run_id, docs), poll_seconds=0.2
        )
        return await run.wait(timeout=timeout), await run.steps()
    finally:
        await transport.close()


def runs_of(docs, job):
    return [
        d.data
        for (c, _), d in docs.data.items()
        if c == runs_collection(PROJECT) and d.data["job"] == job
    ]


class World:
    """What the stubbed seams did, and the gates that hold them."""

    def __init__(self):
        self.fetches: Counter[str] = Counter()
        self.pipeline: Counter[str] = Counter()
        self.synced: list[list[str]] = []
        self.published = 0
        self.fetch_gate: threading.Event | None = None
        self.pipeline_gate: threading.Event | None = None
        self.in_graph: set[str] = set()
        self.in_dataset: set[str] = set()
        self.compactions = 0
        self.builds = 0


@pytest.fixture
def world(monkeypatch):
    world = World()

    def fetch(module, config, *args, **kwargs):
        world.fetches[config.name] += 1
        while world.fetch_gate is not None and not world.fetch_gate.is_set():
            time.sleep(0.01)
        return {
            "file_paths": list(PATHS),
            "total_new_tweets": 3,
            "budget_blocked": False,
            "budget_reason": None,
        }

    def pipeline(path, **kwargs):
        world.pipeline[path] += 1
        while (
            path == PATHS[0]
            and world.pipeline_gate is not None
            and not world.pipeline_gate.is_set()
        ):
            time.sleep(0.01)
        world.in_graph.add(path)

    def sync(module, paths, **kwargs):
        world.synced.append(list(paths))
        world.in_dataset |= set(paths)
        return {"batches": 1}

    def publish(module, **kwargs):
        world.published += 1
        return {"queries": 1}

    monkeypatch.setattr(search, "fetch_search_envelopes", fetch)
    monkeypatch.setattr(search, "search_budget_blocked", lambda module, config: None)
    monkeypatch.setattr(search, "sync_x_dataset_paths_batched", sync)
    monkeypatch.setattr(search, "publish_x_app", publish)
    monkeypatch.setattr(mapping, "envelope_exists", lambda module, path: True)
    monkeypatch.setattr(mapping, "run_search_pipeline_for_file", pipeline)
    monkeypatch.setattr(
        mapping,
        "search_envelope_ingested",
        lambda m, p, graph_name=None: p in world.in_graph,
    )
    monkeypatch.setattr(
        mapping,
        "search_envelope_fully_projected",
        lambda m, p, graph_name=None: p in world.in_graph and p in world.in_dataset,
    )
    monkeypatch.setattr(reprocess, "sync_x_dataset_paths_batched", sync)
    monkeypatch.setattr(reprocess, "publish_x_app", publish)
    monkeypatch.setattr(
        reprocess,
        "list_envelope_paths",
        lambda storage, prefix, cutoff=None: (list(PATHS), 0),
    )
    monkeypatch.setattr(reprocess, "mapped_file_paths", lambda *a: set(world.in_graph))
    monkeypatch.setattr(
        reprocess, "envelope_paths_in_dataset", lambda m, paths: set(world.in_dataset)
    )
    monkeypatch.setattr(common, "publish_x_app", lambda module, **kw: {"app": True})
    monkeypatch.setattr(
        maintenance,
        "run_media_batch",
        lambda module: (
            world.__setattr__("builds", world.builds + 1) or {"processed": 0}
        ),
    )
    monkeypatch.setattr(
        maintenance,
        "run_compaction",
        lambda module: (
            world.__setattr__("compactions", world.compactions + 1) or {"files": {}}
        ),
    )
    return world


def test_a_search_run_fans_out_the_mapping_and_survives_a_kill_without_refetching(
    broker, world
):
    docs = Documents()
    world.pipeline_gate = threading.Event()  # the first envelope's mapping hangs
    module, first = start_host(broker, docs, search_filter("news", app_publish=True))
    try:
        run = asyncio.run(
            module.get_workflow("search_recent_tweets").start({"filter": "news"})
        )
        wait_for(lambda: world.pipeline[PATHS[0]] == 1)
    finally:
        first.stop()  # the host dies after the fetch, while a child maps
    assert world.fetches == {"news": 1}

    world.pipeline_gate = None  # the mapping works again
    _, second = start_host(broker, docs, search_filter("news", app_publish=True))
    try:
        record, steps = asyncio.run(
            record_of(broker, docs, run.run_id, "search_recent_tweets")
        )
    finally:
        second.stop()

    assert record["status"] == "SUCCEEDED" and record["attempt"] == 2
    assert world.fetches == {"news": 1}  # the retry did not call X again
    children = runs_of(docs, "map_tweet_envelope")
    assert len(children) == 3  # the retry re-attached to them: no new child runs
    assert {c["status"] for c in children} == {"SUCCEEDED"}
    assert set(world.in_graph) == set(PATHS)
    assert world.synced and set(world.synced[-1]) == set(PATHS)
    assert world.published == 1
    by_key = {s["key"]: s for s in steps}
    assert by_key["fetch"]["attempt"] == 1 and by_key["fetch"]["status"] == "SUCCEEDED"
    assert {"overlap", "budget", "fetch", "dataset", "publish"} <= set(by_key)
    assert {"map[0]", "map[1]", "map[2]"} <= set(by_key)  # one per child run
    assert record["result"]["mapped"] == 3 and record["result"]["envelopes"] == 3


def test_an_overlapping_tick_is_skipped_and_other_filters_run_independently(
    broker, world
):
    docs = Documents()
    world.fetch_gate = threading.Event()
    module, host = start_host(
        broker, docs, search_filter("news"), search_filter("sports")
    )
    try:
        proxy = module.get_workflow("search_recent_tweets")
        first = asyncio.run(proxy.start({"filter": "news"}))
        wait_for(lambda: world.fetches["news"] == 1)  # running: past its overlap check

        overlapping = asyncio.run(proxy.start({"filter": "news"}))
        skipped, _ = asyncio.run(
            record_of(broker, docs, overlapping.run_id, "search_recent_tweets")
        )

        other = asyncio.run(proxy.start({"filter": "sports"}))
        wait_for(lambda: world.fetches["sports"] == 1)  # sports did not wait for news

        world.fetch_gate.set()
        news, _ = asyncio.run(
            record_of(broker, docs, first.run_id, "search_recent_tweets")
        )
        sports, _ = asyncio.run(
            record_of(broker, docs, other.run_id, "search_recent_tweets")
        )
    finally:
        world.fetch_gate.set()
        host.stop()

    assert skipped["status"] == "SKIPPED" and "still running" in skipped["skip_reason"]
    assert (news["status"], sports["status"]) == ("SUCCEEDED", "SUCCEEDED")
    assert world.fetches == {
        "news": 1,
        "sports": 1,
    }  # the overlapping tick never fetched


def test_the_reprocess_workflow_maps_every_envelope_and_is_a_no_op_the_second_time(
    broker, world
):
    docs = Documents()
    module, host = start_host(broker, docs)
    try:
        proxy = module.get_workflow("reprocess_tweet_envelopes")
        first = asyncio.run(proxy.run({"prefix": "x/search_recent_tweets"}, timeout=30))
        second = asyncio.run(
            proxy.run({"prefix": "x/search_recent_tweets"}, timeout=30)
        )
    finally:
        host.stop()

    assert (first.listed, first.mapped, first.skipped) == (3, 3, 0)
    assert (second.listed, second.mapped, second.skipped) == (3, 0, 3)
    assert world.pipeline == {p: 1 for p in PATHS}  # mapped once, not twice
    assert len(world.synced) == 1
    assert (
        len(runs_of(docs, "map_tweet_envelope")) == 3
    )  # the second run started no child


def test_the_mapping_workflow_is_idempotent_when_launched_by_hand(broker, world):
    docs = Documents()
    module, host = start_host(broker, docs)
    try:
        proxy = module.get_workflow("map_tweet_envelope")
        first = asyncio.run(proxy.run({"path": PATHS[1]}, timeout=30))
        world.in_dataset.add(PATHS[1])
        again = asyncio.run(proxy.start({"path": PATHS[1]}))
        record, _ = asyncio.run(
            record_of(broker, docs, again.run_id, "map_tweet_envelope")
        )
    finally:
        host.stop()
    assert first.status == "mapped" and world.pipeline[PATHS[1]] == 1
    assert record["status"] == "SKIPPED"


def test_the_app_build_and_compaction_jobs_run_when_triggered(broker, world):
    docs = Documents()
    module, host = start_host(broker, docs)
    try:
        built = module.trigger_job("build_app")
        compacted = module.trigger_job("compact_dataset")
        wait_for(lambda: world.builds == 1 and world.compactions == 1)
        build, _ = asyncio.run(record_of(broker, docs, built.run_id, "build_app"))
        compaction, _ = asyncio.run(
            record_of(broker, docs, compacted.run_id, "compact_dataset")
        )
    finally:
        host.stop()
    assert build["status"] == "SUCCEEDED" and build["result"]["app"] == {"app": True}
    assert compaction["status"] == "SUCCEEDED" and compaction["result"] == {"files": {}}
