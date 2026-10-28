"""Durable workflows against a real nats-server (>= 2.14): resume after a stop,
fan-out over replicas, re-attaching children, cancel, trigger inputs, notices.

Skipped when ``nats-server`` is not on PATH. Run records and journals use an
in-memory store shared by every host (as if they shared one document service);
everything NATS-side (stream, schedules, consumers, acks, notices) is real.
"""

import asyncio
import contextlib
import shutil
import time
from collections import Counter

import pytest
from nats_broker import running_broker
from test_jobs_integration import PROJECT, _until
from test_workflows import MemoryDocuments, model

from naas_abi_sdk.job_host import JobHost
from naas_abi_sdk.jobs import (
    Cron,
    Every,
    JobDescriptor,
    JobsMixin,
    job_subjects,
    runs_collection,
    stream_name,
)
from naas_abi_sdk.transport import Transport
from naas_abi_sdk.workflows import (
    FlowContext,
    WorkflowProxy,
    WorkflowRunFailed,
    workflow,
)

pytestmark = pytest.mark.skipif(
    shutil.which("nats-server") is None, reason="nats-server not installed"
)

REPORTS, PARENT, CHILD = "acme.reports", "acme.parent", "acme.child"


@pytest.fixture
def broker(tmp_path):
    with running_broker(tmp_path) as url:
        yield url


def _runs_collection():
    return runs_collection(PROJECT)


ReportInput = model("ReportInput", {"n": "integer"}, required=("n",))
ReportOutput = model("ReportOutput", {"total": "integer"}, required=("total",))


def _host(url, docs, module, module_id, **kwargs):
    """A job host for ``module``'s jobs, on a connection of its own."""
    return JobHost(
        Transport(url, "test-token"),
        docs,
        module_id,
        PROJECT,
        {j.name: (j, module._job_handlers[j.name]) for j in module.jobs},
        instance_id=kwargs.pop("instance_id", "i-1"),
        fetch_timeout_seconds=0.2,
        backoff_base_seconds=0.2,
        close_grace_seconds=1.0,
        close_cancel_seconds=2.0,
        module_documents=lambda module_id: docs,
        workflow_poll_seconds=kwargs.pop("workflow_poll_seconds", 0.5),
        **kwargs,
    )


def _proxy(url, docs, module_id, name, **kwargs):
    descriptor = JobDescriptor(name, kind="workflow")
    return WorkflowProxy(
        Transport(url, "t"), PROJECT, module_id, descriptor, docs, **kwargs
    )


@contextlib.asynccontextmanager
async def _running(*hosts):
    for host in hosts:
        await host.start()
    try:
        yield
    finally:
        for host in hosts:
            await host.close()
            await host.transport.close()


class Reports(JobsMixin):
    """A three step workflow with typed input and output."""

    def __init__(self, calls, gate=None):
        self.calls, self.gate = calls, gate

    @workflow(max_attempts=3)
    async def report(self, ctx: FlowContext, inp: ReportInput) -> ReportOutput:
        loaded = await ctx.step("load", self.load, inp.n)
        doubled = await ctx.step("transform", self.transform, loaded)
        total = await ctx.step("publish", self.publish, doubled)
        return ReportOutput(total=total)

    async def load(self, n):
        self.calls["load"] += 1
        return list(range(n))

    async def transform(self, items):
        self.calls["transform"] += 1
        if self.gate is not None:
            await self.gate.wait()
        return [i * 2 for i in items]

    async def publish(self, items):
        self.calls["publish"] += 1
        return sum(items)


def test_a_host_stopped_mid_run_resumes_without_rerunning_finished_steps(broker):
    docs, calls = MemoryDocuments(), Counter()

    async def scenario():
        blocked = Reports(calls, gate=asyncio.Event())  # transform never ends
        first = _host(broker, docs, blocked, REPORTS, instance_id="a")
        async with _running(first):
            run = await _proxy(
                broker, docs, REPORTS, "report", output_type=ReportOutput
            ).start({"n": 4})
            await _until(lambda: calls["transform"] == 1)
        # The host stopped while "transform" ran: the run was interrupted and retried.
        before = docs.steps(run.run_id)
        assert before["load"]["status"] == "SUCCEEDED"
        assert before["transform"]["status"] != "SUCCEEDED"

        async with _running(
            _host(broker, docs, Reports(calls), REPORTS, instance_id="b")
        ):
            output = await run.result(timeout=20)
            return run, output

    run, output = asyncio.run(scenario())

    assert output.total == 12  # 0+2+4+6, a typed model
    assert calls == {"load": 1, "transform": 2, "publish": 1}  # "load" ran once
    record = asyncio.run(run.status())
    assert record["status"] == "SUCCEEDED" and record["attempt"] == 2
    steps = {s["key"]: s for s in asyncio.run(run.steps())}
    assert [steps[k]["status"] for k in ("load", "transform", "publish")] == [
        "SUCCEEDED"
    ] * 3
    assert steps["load"]["attempt"] == 1 and steps["transform"]["attempt"] == 2


class Children(JobsMixin):
    def __init__(self, instance, executions, gate=None, pause=0.0):
        self.instance, self.executions = instance, executions
        self.gate, self.pause = gate, pause

    @workflow(max_concurrency=2)
    async def child(self, ctx: FlowContext, inp: dict) -> dict:
        self.executions.append((self.instance, inp["i"]))
        if self.gate is not None:
            await self.gate.wait()
        await asyncio.sleep(self.pause)
        return {"i": inp["i"], "by": self.instance}

    @workflow()
    async def hang(self, ctx: FlowContext, inp: dict) -> dict:
        self.executions.append((self.instance, "hang"))
        await ctx.cancelled.wait()
        return {}


class Parent(JobsMixin):
    @workflow(max_attempts=3)
    async def fan(self, ctx: FlowContext, inp: dict) -> dict:
        results = await ctx.map_call(
            "fan",
            CHILD,
            "child",
            [{"i": i} for i in range(inp["count"])],
            concurrency=inp.get("concurrency", 4),
        )
        return {
            "by": sorted({r["by"] for r in results}),
            "order": [r["i"] for r in results],
        }

    @workflow()
    async def outer(self, ctx: FlowContext, inp: dict) -> dict:
        return await ctx.call(CHILD, "hang", {})

    @workflow(max_attempts=3)
    async def loop(self, ctx: FlowContext, inp: dict) -> dict:
        return await ctx.call(PARENT, "loop", {})


def test_map_call_fans_out_across_replicas(broker):
    docs, executions = MemoryDocuments(), []

    async def scenario():
        replicas = [
            _host(
                broker,
                docs,
                Children(instance, executions, pause=0.15),
                CHILD,
                instance_id=instance,
            )
            for instance in ("one", "two")
        ]
        parent = _host(broker, docs, Parent(), PARENT)
        async with _running(*replicas, parent):
            return await _proxy(broker, docs, PARENT, "fan").run(
                {"count": 10, "concurrency": 6}, timeout=30
            )

    out = asyncio.run(scenario())

    assert out["order"] == list(range(10))  # outputs keep the order of the inputs
    assert sorted(i for _, i in executions) == list(range(10))  # once each
    assert out["by"] == ["one", "two"]  # whichever replica took each child


def test_a_replayed_parent_reattaches_to_its_children_instead_of_starting_new_ones(
    broker,
):
    docs, executions = MemoryDocuments(), []
    gate = asyncio.Event()

    async def scenario():
        replicas = [
            _host(
                broker,
                docs,
                Children(instance, executions, gate=gate),
                CHILD,
                instance_id=instance,
            )
            for instance in ("one", "two")
        ]
        async with _running(*replicas):
            first = _host(broker, docs, Parent(), PARENT, instance_id="p1")
            async with _running(first):
                run = await _proxy(broker, docs, PARENT, "fan").start(
                    {"count": 6, "concurrency": 2}
                )
                await _until(lambda: len(executions) == 2)
            # The parent's host stopped with two children running; their ids are journaled.
            journaled = {
                k: s["child"]["run_id"]
                for k, s in docs.steps(run.run_id).items()
                if s.get("child")
            }
            assert sorted(journaled) == ["fan[0]", "fan[1]"]
            async with _running(
                _host(broker, docs, Parent(), PARENT, instance_id="p2")
            ):
                await _until(
                    lambda: (
                        docs.data[(_runs_collection(), run.run_id)].data["attempt"] == 2
                    )
                )
                gate.set()
                output = await run.result(timeout=30)
            return run, output, journaled

    run, output, journaled = asyncio.run(scenario())

    assert output["order"] == list(range(6))
    # Six children ran, once each: the replay waited for the two it had started.
    assert sorted(i for _, i in executions) == list(range(6))
    steps = docs.steps(run.run_id)
    assert {k: steps[k]["child"]["run_id"] for k in journaled} == journaled
    assert all(steps[f"fan[{i}]"]["status"] == "SUCCEEDED" for i in range(6))


def test_a_waiting_parent_keeps_its_slot_and_its_heartbeats(broker):
    docs, executions = MemoryDocuments(), []

    async def scenario():
        children = _host(broker, docs, Children("one", executions, pause=2.5), CHILD)
        # An acknowledgement wait of 1 s: without heartbeats the broker would
        # redeliver the parent while it waits for its child.
        parent = _host(
            broker, docs, Parent(), PARENT, ack_wait_seconds=1.0, heartbeat_seconds=0.3
        )
        async with _running(children, parent):
            proxy = _proxy(broker, docs, PARENT, "fan")
            first = await proxy.start({"count": 1})
            second = await proxy.start({"count": 1})
            await asyncio.gather(first.wait(timeout=60), second.wait(timeout=60))
            return first, second

    first, second = asyncio.run(scenario())

    one, two = (docs.data[(_runs_collection(), r.run_id)].data for r in (first, second))
    assert one["status"] == two["status"] == "SUCCEEDED"
    assert one["attempt"] == two["attempt"] == 1  # never redelivered
    assert len(executions) == 2  # one child per parent
    # max_concurrency is 1: the second parent starts once the first has ended.
    assert two["started_at"] >= one["finished_at"]


def test_cancelling_a_parent_cancels_its_running_children(broker):
    docs, executions = MemoryDocuments(), []

    async def scenario():
        children = _host(broker, docs, Children("one", executions), CHILD)
        parent = _host(broker, docs, Parent(), PARENT)
        async with _running(children, parent):
            run = await _proxy(broker, docs, PARENT, "outer").start({})
            await _until(lambda: executions == [("one", "hang")])
            child_run = next(
                s["child"]["run_id"]
                for s in docs.steps(run.run_id).values()
                if s.get("child")
            )
            await run.cancel()
            record = await run.wait(timeout=15)
            child_key = (_runs_collection(), child_run)
            await _until(lambda: docs.data[child_key].data["status"] == "CANCELLED")
            return record, docs.data[child_key].data, docs.steps(run.run_id)

    record, child, steps = asyncio.run(scenario())

    assert record["status"] == "CANCELLED" and child["status"] == "CANCELLED"
    assert {s["status"] for s in steps.values()} == {"CANCELLED"}


def test_a_workflow_that_calls_itself_fails_at_once(broker):
    docs = MemoryDocuments()

    async def scenario():
        async with _running(_host(broker, docs, Parent(), PARENT)):
            with pytest.raises(WorkflowRunFailed, match="cannot call itself") as caught:
                await _proxy(broker, docs, PARENT, "loop").run({}, timeout=15)
            return caught.value

    failure = asyncio.run(scenario())

    assert failure.status == "FAILED"
    record = docs.data[(_runs_collection(), failure.run_id)].data
    assert record["attempt"] == 1  # max_attempts is 3: refusing is not retried


def test_run_returns_the_typed_output_and_a_notice_ends_the_wait(broker):
    docs, calls = MemoryDocuments(), Counter()

    async def scenario():
        async with _running(_host(broker, docs, Reports(calls), REPORTS)):
            # A 60 s poll: only the host's completion notice can end the wait early.
            proxy = _proxy(
                broker,
                docs,
                REPORTS,
                "report",
                input_type=ReportInput,
                output_type=ReportOutput,
                poll_seconds=60,
            )
            started = time.monotonic()
            output = await proxy.run(ReportInput(n=3), timeout=30)
            elapsed = time.monotonic() - started
            run = await proxy.start({"n": 2})
            await run.wait(timeout=30)
            invalid = await _proxy(
                broker, docs, REPORTS, "report", poll_seconds=60
            ).start({})  # no "n"
            return output, elapsed, await run.steps(), await invalid.wait(timeout=15)

    output, elapsed, steps, record = asyncio.run(scenario())

    assert (output.total, calls["publish"]) == (6, 2)
    assert elapsed < 15
    assert [s["key"] for s in steps] == ["load", "transform", "publish"]
    # An invalid input fails the run without a retry, though max_attempts is 3.
    assert record["status"] == "FAILED" and record["attempt"] == 1
    assert "InvalidWorkflowInput" in record["error"]


def test_a_module_runs_its_own_workflow_through_its_bound_host(broker):
    docs, calls = MemoryDocuments(), Counter()

    async def scenario():
        module = Reports(calls)
        host = _host(broker, docs, module, REPORTS)
        async with _running(host):
            module._bind_job_host(host, asyncio.get_running_loop())
            try:
                output = await module.get_workflow("report").run({"n": 3}, timeout=30)
            finally:
                module._bind_job_host(None, None)
            return output

    assert asyncio.run(scenario()).total == 6


# --- triggers with an input ------------------------------------------------------------


def test_a_schedule_delivers_its_input_as_the_run_payload(broker):
    docs, seen = MemoryDocuments(), []

    class Digests(JobsMixin):
        @workflow(triggers=(Every("1s", input={"filter": "db", "limit": 5}),))
        async def digest(self, ctx: FlowContext, inp: dict) -> dict:
            seen.append((inp, ctx.trigger["kind"]))
            return inp

    async def scenario():
        async with _running(_host(broker, docs, Digests(), "acme.digests")):
            await _until(lambda: seen, timeout=15)

    asyncio.run(scenario())

    assert seen[0] == ({"filter": "db", "limit": 5}, "schedule")


def test_a_changed_trigger_input_republishes_only_that_schedule(broker):
    docs = MemoryDocuments()

    def digests(first, cron):
        class Digests(JobsMixin):
            @workflow(
                triggers=(
                    Every("1h", input=first),
                    Every("2h", input={"fixed": True}),
                    Cron("@daily", input=cron),
                )
            )
            async def digest(self, ctx: FlowContext, inp: dict) -> dict:
                return inp

        return Digests()

    async def scenario():
        subjects = job_subjects(PROJECT, "acme.digests", "digest")
        transport = Transport(broker, "t")
        js = (await transport.connect()).jetstream()

        async def schedules():
            found = {}
            for index in range(3):
                message = await js.get_last_msg(
                    stream_name(PROJECT), subjects.schedule(index)
                )
                found[index] = (message.seq, message.data)
            return found

        try:
            async with _running(
                _host(broker, docs, digests({"n": 1}, {"k": 1}), "acme.digests")
            ):
                first = await schedules()
            async with _running(
                _host(broker, docs, digests({"n": 1}, {"k": 1}), "acme.digests")
            ):
                restarted = await schedules()
            async with _running(
                _host(broker, docs, digests({"n": 2}, {"k": 1}), "acme.digests")
            ):
                changed = await schedules()
            return first, restarted, changed
        finally:
            # Not nc.close(): only the transport's own close is no connection loss.
            await transport.close()

    first, restarted, changed = asyncio.run(scenario())

    assert first[0][1] == b'{"n":1}' and first[1][1] == b'{"fixed":true}'
    assert (
        restarted == first
    )  # a restart leaves every schedule (and its interval) alone
    assert changed[0][0] > first[0][0] and changed[0][1] == b'{"n":2}'
    assert changed[1] == first[1] and changed[2] == first[2]


# --- Workflow and Pipeline classes of a remote module (extras: workflows, rdf) ---------

PROCESSES = "acme.process"


def _process_module():
    """A module whose pipeline runs every second, and whose workflow runs when started."""
    pytest.importorskip("pydantic")
    pytest.importorskip("rdflib")
    from unittest.mock import MagicMock

    from rdflib import Graph, Literal, URIRef

    from naas_abi_sdk.jobs import JobSettings
    from naas_abi_sdk.module import BaseModule
    from naas_abi_sdk.pipeline import Pipeline, PipelineParameters
    from naas_abi_sdk.workflow import Workflow, WorkflowParameters

    class TickParameters(PipelineParameters):
        count: int = 2

    class TickPipeline(Pipeline[TickParameters]):
        """Writes a few triples."""

        job = JobSettings(triggers=(Every("1s"),))

        async def run(self, parameters: TickParameters) -> Graph:
            graph = Graph()
            for index in range(parameters.count):
                graph.add(
                    (
                        URIRef(f"http://example.org/s{index}"),
                        URIRef("http://example.org/p"),
                        Literal(f"v{index}"),
                    )
                )
            return graph

    class AddParameters(WorkflowParameters):
        a: int
        b: int

    class AddWorkflow(Workflow[AddParameters]):
        """Adds two numbers."""

        async def run(self, parameters: AddParameters):
            return {"sum": parameters.a + parameters.b}

    class ABIModule(BaseModule):
        module_id = PROCESSES
        workflows = (AddWorkflow,)
        pipelines = (TickPipeline,)

    module = ABIModule(MagicMock(), ABIModule.Configuration())
    module.declare_process_workflows()
    asyncio.run(module.build_processes())
    return module


def _records(docs, workflow_name):
    return [
        doc.data
        for (collection, _), doc in docs.data.items()
        if collection == _runs_collection() and doc.data.get("job") == workflow_name
    ]


def test_a_scheduled_pipeline_class_runs_in_its_module_and_records_its_graph(broker):
    docs, module = MemoryDocuments(), _process_module()  # skips without the extras
    from rdflib import Graph

    def succeeded():
        return [
            r
            for r in _records(docs, "pipeline.tick_pipeline")
            if r["status"] == "SUCCEEDED"
        ]

    async def scenario():
        async with _running(_host(broker, docs, module, PROCESSES)):
            await _until(succeeded, timeout=15)

    asyncio.run(scenario())

    (done, *_) = succeeded()
    assert done["trigger"]["kind"] == "schedule"
    assert done["result"]["format"] == "text/turtle" and done["result"]["triples"] == 2
    assert len(Graph().parse(data=done["result"]["data"], format="turtle")) == 2
    assert (
        _records(docs, "workflow.add_workflow") == []
    )  # no trigger: only when started


def test_another_module_starts_a_workflow_class_and_reads_its_output(broker):
    docs, module = MemoryDocuments(), _process_module()
    (descriptor,) = [j for j in module.jobs if j.name == "workflow.add_workflow"]

    async def scenario():
        async with _running(_host(broker, docs, module, PROCESSES)):
            proxy = WorkflowProxy(
                Transport(broker, "t"), PROJECT, PROCESSES, descriptor, docs
            )
            try:
                output = await proxy.run({"a": 2, "b": 3}, timeout=30)
                run = await proxy.start({"a": 1, "b": 1}, idempotency_key="sum-1")
                again = await proxy.start({"a": 1, "b": 1}, idempotency_key="sum-1")
                await run.wait(timeout=30)
                refused = await (await proxy.start({"a": "x"})).wait(timeout=30)
                return output, run, again, await run.steps(), refused
            finally:
                await proxy.transport.close()

    output, run, again, steps, refused = asyncio.run(scenario())

    assert output == {"sum": 5}
    assert again.run_id == run.run_id and again.duplicate
    assert [s["key"] for s in steps] == ["run"]
    # Parameters the model refuses fail the run at once, naming the fields.
    assert refused["status"] == "FAILED" and refused["attempt"] == 1
    assert "a" in refused["error"] and "b" in refused["error"]
