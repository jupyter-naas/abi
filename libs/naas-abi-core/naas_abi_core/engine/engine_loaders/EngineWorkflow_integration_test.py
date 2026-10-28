"""Engine module workflows on a real broker; requires a local nats-server (>= 2.14).

Run records and journals live in an in-memory store shared by every loader (as if
they shared one Document Service); the stream, consumers, acks, notices and
schedules are real.
"""

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
from naas_abi_core.engine.engine_loaders.EngineProcessBridge import bridge_processes
from naas_abi_core.engine.engine_loaders.EngineProcessBridge_test import (
    ReportWorkflow,
    TweetsPipeline,
)
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.module.jobs import JobsMixin
from naas_abi_core.module.workflows import SyncFlowContext, workflow
from naas_abi_core.module.workflows_test import Documents
from naas_abi_core.pipeline.pipeline import PipelineConfiguration
from naas_abi_core.workflow.workflow import WorkflowConfiguration
from naas_abi_sdk.jobs import JobRun, runs_collection
from naas_abi_sdk.transport import Transport
from naas_abi_sdk.workflows import WorkflowRun, WorkflowRunFailed
from pydantic import BaseModel

PROJECT = "witest"
REPORTS, SINK, BRIDGED = "acme.reports", "acme.sink", "acme.bridged"
pytestmark = pytest.mark.integration


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


def _wait(predicate, timeout=15.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not met in time")
        time.sleep(0.05)


def _config(url):
    return NATSConfiguration(
        nats_url=url,
        discovery=DiscoveryConfiguration(project=PROJECT),
        jobs=NATSJobsConfiguration(interrupt_grace_seconds=0.2),
    )


def _loader(url, docs):
    return EngineJobLoader(
        _config(url),
        credentials=TEST_TOKENS.source("engine"),
        documents_factory=lambda transport, module_id: docs,
        host_options={
            "fetch_timeout_seconds": 0.2,
            "backoff_base_seconds": 0.2,
            "close_grace_seconds": 0.5,
            "close_cancel_seconds": 2.0,
            "workflow_poll_seconds": 0.5,
        },
    )


class ReportInput(BaseModel):
    n: int


class ReportOutput(BaseModel):
    total: int
    pushed: int
    fanned: int


class Reports(JobsMixin):
    """A multi-step sync workflow of an engine module."""

    _sync_jobs = True

    def __init__(self, calls, gate=None):
        self.calls, self.gate = calls, gate

    @workflow(max_attempts=3)
    def report(self, ctx: SyncFlowContext, inp: ReportInput) -> ReportOutput:
        rows = ctx.step("load", self.load, inp.n)
        doubled = ctx.step("transform", self.transform, rows)
        pushed = ctx.call(SINK, "push", {"rows": doubled})
        fanned = ctx.map_call("fan", SINK, "push", [{"rows": [i]} for i in range(3)])
        total = ctx.step("publish", self.publish, doubled)
        return ReportOutput(total=total, pushed=pushed["count"], fanned=len(fanned))

    def load(self, n):
        self.calls["load"] += 1
        return list(range(n))

    def transform(self, rows):
        self.calls["transform"] += 1
        # Blocks like engine code does, but where an interrupt can reach it.
        while self.gate is not None and not self.gate.is_set():
            time.sleep(0.01)
        return [r * 2 for r in rows]

    def publish(self, doubled):
        self.calls["publish"] += 1
        return sum(doubled)


class Sink(JobsMixin):
    _sync_jobs = True

    def __init__(self, calls):
        self.calls = calls

    @workflow(max_concurrency=4)
    def push(self, ctx: SyncFlowContext, inp: dict) -> dict:
        self.calls["push"] += 1
        return {"count": len(inp["rows"]), "thread": threading.current_thread().name}


class Bridged(JobsMixin):
    _sync_jobs = True

    def __init__(self):
        self.pipelines = [TweetsPipeline(PipelineConfiguration())]
        self.workflows = [ReportWorkflow(WorkflowConfiguration())]


def _attach(transport, docs, run_id, module_id, name, **kwargs):
    return WorkflowRun(
        JobRun(transport, PROJECT, module_id, name, run_id, docs), **kwargs
    )


async def _record(url, docs, run_id, module_id, name, timeout=30):
    transport = Transport(url, TEST_TOKENS.token("caller"))
    try:
        run = _attach(transport, docs, run_id, module_id, name, poll_seconds=0.2)
        return await run.wait(timeout=timeout), await run.steps()
    finally:
        await transport.close()


def test_a_sync_workflow_survives_a_host_restart_and_calls_another_module(broker):
    docs, calls = Documents(), Counter()
    stuck = Reports(calls, gate=threading.Event())  # transform waits for this
    first = _loader(broker, docs)
    first.start({REPORTS: stuck, SINK: Sink(calls)}, document_available=True)
    try:
        # Through the module itself, as engine.modules[REPORTS].get_workflow(...) is.
        run = asyncio.run(stuck.get_workflow("report").start({"n": 4}))
        _wait(lambda: calls["transform"] == 1)
    finally:
        first.stop()  # the host goes while "transform" runs: the run is retried
    assert calls["load"] == 1 and calls["push"] == 0

    second = _loader(broker, docs)
    second.start({REPORTS: Reports(calls), SINK: Sink(calls)}, document_available=True)
    try:
        record, steps = asyncio.run(
            _record(broker, docs, run.run_id, REPORTS, "report")
        )
    finally:
        second.stop()

    assert record["status"] == "SUCCEEDED" and record["attempt"] == 2
    assert record["result"] == {"total": 12, "pushed": 4, "fanned": 3}  # 0+2+4+6
    assert calls == {"load": 1, "transform": 2, "publish": 1, "push": 4}
    by_key = {s["key"]: s for s in steps}
    assert by_key["load"]["attempt"] == 1 and by_key["transform"]["attempt"] == 2
    assert {k for k, s in by_key.items() if s["kind"] == "call"} >= {"fan[0]", "fan[2]"}
    assert all(s["status"] == "SUCCEEDED" for s in steps)
    child = next(s for k, s in by_key.items() if k.startswith("call:"))
    assert child["child"]["module_id"] == SINK  # re-attachable by id


def test_engine_modules_run_each_others_workflows_through_get_workflow(broker):
    docs, calls = Documents(), Counter()
    sink, reports = Sink(calls), Reports(calls)
    loader = _loader(broker, docs)
    loader.start({REPORTS: reports, SINK: sink}, document_available=True)
    try:

        async def scenario():
            # engine.modules["acme.sink"].get_workflow("push"), from another module's code
            pushed = await sink.get_workflow("push").run({"rows": [1, 2]}, timeout=20)
            report = await reports.get_workflow("report").run({"n": 2}, timeout=30)
            # a module that is not engine-hosted here, by id, through the engine's connection
            by_id = await loader.workflow(SINK, "push").run({"rows": []}, timeout=20)
            return pushed, report, by_id

        pushed, report, by_id = asyncio.run(scenario())
    finally:
        loader.stop()

    assert pushed["count"] == 2 and pushed["thread"].startswith("abi-job-")
    assert report == ReportOutput(total=2, pushed=2, fanned=3)  # typed, as declared
    assert by_id["count"] == 0


def test_bridged_workflows_and_pipelines_are_started_and_awaited_by_name(broker):
    docs = Documents()
    module = Bridged()
    config = _config(broker)
    declared = bridge_processes({BRIDGED: module}, config)
    assert sorted(declared) == [
        f"{BRIDGED}:pipeline.tweets_pipeline",
        f"{BRIDGED}:workflow.report_workflow",
    ]
    assert all(j.kind == "workflow" and j.input_schema for j in module.jobs)

    loader = _loader(broker, docs)
    loader.start({BRIDGED: module}, document_available=True)
    try:

        async def scenario():
            graph = await loader.workflow(BRIDGED, "pipeline.tweets_pipeline").run(
                {"query": "db", "limit": 3}, timeout=20
            )
            started = await module.get_workflow("workflow.report_workflow").start(
                {"name": "abi"}
            )
            greeting = await started.result(timeout=20)
            invalid = await loader.workflow(BRIDGED, "pipeline.tweets_pipeline").start(
                {"limit": 3}
            )
            with pytest.raises(WorkflowRunFailed, match="query"):
                await invalid.result(timeout=20)
            return graph, greeting, await started.steps(), await invalid.status()

        graph, greeting, steps, invalid = asyncio.run(scenario())
    finally:
        loader.stop()

    assert graph["format"] == "text/turtle" and graph["triples"] == 3
    assert "urn:t:0" in graph["data"]
    assert greeting == {"greeting": "hello abi"}
    assert [(s["key"], s["status"]) for s in steps] == [("run", "SUCCEEDED")]
    assert invalid["status"] == "FAILED" and invalid["attempt"] == 1
    runs = [
        d.data
        for (c, _), d in docs.data.items()
        if c == runs_collection(PROJECT)
        and d.data.get("job", "").startswith("pipeline.")
    ]
    assert {r["status"] for r in runs} == {"SUCCEEDED", "FAILED"}
