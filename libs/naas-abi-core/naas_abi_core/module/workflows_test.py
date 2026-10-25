import asyncio
import json
import threading
import time
from collections import Counter
from datetime import UTC, datetime

import pytest
from naas_abi_core.engine.engine_loaders.EngineJobLoader import as_async_handler
from naas_abi_core.engine.engine_loaders.SyncJobRunner import (
    JobInterrupted,
    SyncJobRunner,
)
from naas_abi_core.module.jobs import JobsMixin
from naas_abi_core.module.workflows import (
    FlowContext,
    InvalidWorkflowInput,
    StepKeyError,
    SyncFlowContext,
    WorkflowCancelled,
    workflow,
)
from naas_abi_sdk.jobs import JobDescriptor
from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict
from naas_abi_sdk.services.models import Document, Page
from naas_abi_sdk.workflows import FlowRuntime
from pydantic import BaseModel


class Documents:
    """An in-memory document store with CAS and the one filter the journal uses."""

    def __init__(self):
        self.data: dict[tuple[str, str], Document] = {}
        self.lock = threading.Lock()

    async def ensure_collection(self, spec):
        return None

    async def get(self, collection, id):
        with self.lock:
            try:
                return self.data[(collection, id)]
            except KeyError:
                raise DocumentNotFound("NOT_FOUND", id) from None

    async def put(self, collection, id, data, *, if_version=None):
        with self.lock:
            current = self.data.get((collection, id))
            if if_version == 0 and current is not None:
                raise VersionConflict("VERSION_CONFLICT", id)
            if if_version and (current is None or current.version != if_version):
                raise VersionConflict("VERSION_CONFLICT", id)
            now = datetime.now(UTC)
            doc = Document(
                id=id,
                data=json.loads(json.dumps(data)),
                created_at=current.created_at if current else now,
                updated_at=now,
                version=(current.version + 1) if current else 1,
            )
            self.data[(collection, id)] = doc
            return doc

    async def find(
        self, collection, *, where=(), order_by=None, limit=100, cursor=None, **_
    ):
        def matches(data):
            for field, op, value in where:
                have = data.get(field)
                if op == "eq" and have != value:
                    return False
                if op == "in" and have not in value:
                    return False
                if op == "lt" and not (have is not None and have < value):
                    return False
            return True

        with self.lock:
            items = [d for (c, _), d in self.data.items() if c == collection]
        items = [d for d in items if matches(d.data)]
        if order_by:
            items.sort(key=lambda d: d.data.get(order_by[0], ""))
        return Page(items[:limit], None)

    async def delete(self, collection, id, *, if_version=None):
        with self.lock:
            if (collection, id) not in self.data:
                raise DocumentNotFound("NOT_FOUND", id)
            del self.data[(collection, id)]

    async def count(self, collection, where=()):
        return len((await self.find(collection, where=where, limit=10**6)).items)

    def statuses(self):
        with self.lock:
            return {
                d.data["key"]: d.data["status"]
                for (c, _), d in self.data.items()
                if c.startswith("workflow_steps_")
            }


class LoopThread:
    """The job host's loop, on a thread of its own."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def run(self, coro, timeout=10):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def close(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(5)
        self.loop.close()


@pytest.fixture
def host_loop():
    loop = LoopThread()
    yield loop
    loop.close()


def _flow(docs, run_id="wf:1", payload=None):
    return FlowContext(
        run_id,
        "wf",
        1,
        {"kind": "manual"},
        payload or {},
        runtime=FlowRuntime(None, docs, "acme.mod", "p", poll_seconds=0.05),
        fired_at="t0",
    )


def _sync_ctx(docs, host_loop, **kwargs):
    return SyncFlowContext(_flow(docs, **kwargs), host_loop.loop)


def test_a_step_runs_in_the_handler_thread_and_is_journaled(host_loop):
    docs, calls = Documents(), Counter()

    def load(n):
        calls["load"] += 1
        return {"rows": list(range(n)), "thread": threading.current_thread().name}

    first = _sync_ctx(docs, host_loop).step("load", load, 3)
    again = _sync_ctx(docs, host_loop).step("load", load, 3)  # a retry of the run

    assert first["rows"] == [0, 1, 2]
    assert first["thread"] == threading.current_thread().name
    assert again == first
    assert calls == {"load": 1}  # the stored result came back, fn did not run
    assert docs.statuses() == {"load": "SUCCEEDED"}


def test_a_failed_step_retries_locally_then_raises(host_loop):
    docs, calls = Documents(), Counter()

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("down")
        return "ok"

    ctx = _sync_ctx(docs, host_loop)
    assert ctx.step("flaky", flaky, retries=2, backoff=0.01) == "ok"
    assert calls["n"] == 3

    def broken():
        raise ValueError("bad")

    with pytest.raises(ValueError, match="bad"):
        ctx.step("broken", broken)
    assert docs.statuses()["broken"] == "FAILED"


def test_step_keys_stay_unique_within_a_run(host_loop):
    ctx = _sync_ctx(Documents(), host_loop)
    ctx.step("once", lambda: 1)

    with pytest.raises(StepKeyError):
        ctx.step("once", lambda: 2)


def test_async_functions_are_steps_too(host_loop):
    async def fetch(x):
        await asyncio.sleep(0)
        return x * 2

    assert _sync_ctx(Documents(), host_loop).step("fetch", fetch, 4) == 8


def test_map_journals_each_item_and_keeps_the_order(host_loop):
    docs, seen = Documents(), []

    def double(x):
        seen.append(threading.current_thread().name)
        time.sleep(0.02)
        return x * 2

    ctx = _sync_ctx(docs, host_loop)
    assert ctx.map("double", [1, 2, 3, 4], double, concurrency=2) == [2, 4, 6, 8]

    assert docs.statuses() == {f"double[{i}]": "SUCCEEDED" for i in range(4)}
    assert len(set(seen)) == 2  # two worker threads
    assert threading.current_thread().name not in seen
    with pytest.raises(StepKeyError):
        ctx.map("double", [1], double)  # the map's key is taken


def test_map_stops_at_the_first_failure_and_keeps_finished_items(host_loop):
    docs = Documents()

    def work(x):
        if x == 1:
            raise RuntimeError("item 1 failed")
        return x

    with pytest.raises(RuntimeError, match="item 1 failed"):
        _sync_ctx(docs, host_loop).map("w", [0, 1, 2, 3], work, concurrency=1)

    statuses = docs.statuses()
    assert statuses["w[0]"] == "SUCCEEDED" and statuses["w[1]"] == "FAILED"


class _ReportInput(BaseModel):
    n: int


class _ReportOutput(BaseModel):
    total: int


class _Module(JobsMixin):
    _sync_jobs = True

    def __init__(self, calls):
        self.calls = calls

    @workflow(max_attempts=3)
    def report(self, ctx: SyncFlowContext, inp: _ReportInput) -> _ReportOutput:
        """Sums doubled rows."""
        rows = ctx.step("load", self.load, inp.n)
        return _ReportOutput(total=ctx.step("sum", lambda: sum(r * 2 for r in rows)))

    def load(self, n):
        self.calls["load"] += 1
        return list(range(n))

    @workflow()
    async def async_one(self, ctx: FlowContext, inp: dict) -> dict:
        return {"async": True}


def test_a_sync_workflow_is_declared_like_an_sdk_one():
    descriptors = {j.name: j for j in _Module.jobs}

    report = descriptors["report"]
    assert report.kind == "workflow" and report.max_attempts == 3
    assert report.description == "Sums doubled rows."
    assert json.loads(report.input_schema)["properties"] == {
        "n": {"title": "N", "type": "integer"}
    }
    assert json.loads(report.output_schema)["required"] == ["total"]
    assert descriptors["async_one"].kind == "workflow"
    spec = _Module(Counter()).workflow_spec("report")
    assert spec.input_type is _ReportInput and spec.output_type is _ReportOutput


def test_a_sync_workflow_runs_in_a_worker_thread_through_the_engine_runner():
    docs, calls = Documents(), Counter()
    module = _Module(calls)
    handler = as_async_handler(
        module._job_handlers["report"], interrupt_grace_seconds=2
    )
    assert isinstance(handler, SyncJobRunner)

    async def run(payload):
        return await handler(_flow(docs, payload=payload))

    assert asyncio.run(run({"n": 4})) == {"total": 12}  # 0+2+4+6, the output dumped
    assert calls == {"load": 1}
    with pytest.raises(InvalidWorkflowInput):
        asyncio.run(run({"n": "many"}))
    assert calls == {"load": 1}  # an invalid input never reaches the handler


def test_async_workflows_keep_the_sdk_handler():
    handler = _Module(Counter())._job_handlers["async_one"]

    assert asyncio.run(handler(_flow(Documents()))) == {"async": True}
    assert as_async_handler(handler) is handler


def test_a_skipped_sync_workflow_has_no_output():
    class Skipper(JobsMixin):
        _sync_jobs = True

        @workflow()
        def maybe(self, ctx: SyncFlowContext, inp: dict) -> _ReportOutput:
            ctx.skip("nothing to do")
            return None  # type: ignore[return-value]

    handler = as_async_handler(
        Skipper()._job_handlers["maybe"], interrupt_grace_seconds=1
    )

    assert asyncio.run(handler(_flow(Documents()))) is None


def test_declare_workflow_accepts_a_sync_handler_at_runtime():
    module = _Module(Counter())

    def handler(ctx, inp):
        return ctx.step("go", lambda: {"got": inp.n})

    descriptor = module.declare_workflow(
        "workflow.dyn", handler, input_type=_ReportInput, description="Dynamic."
    )

    assert descriptor.kind == "workflow" and descriptor.description == "Dynamic."
    assert module.workflow_spec("workflow.dyn").input_type is _ReportInput
    assert "workflow.dyn" in module._job_handlers
    assert "workflow.dyn" in {j.name for j in module.jobs}
    assert "workflow.dyn" not in {j.name for j in _Module.jobs}  # this instance only
    wrapped = as_async_handler(
        module._job_handlers["workflow.dyn"], interrupt_grace_seconds=1
    )
    assert asyncio.run(wrapped(_flow(Documents(), payload={"n": 7}))) == {"got": 7}


def test_declare_workflow_still_takes_async_handlers():
    module = _Module(Counter())

    async def handler(ctx, inp):
        return {"ok": True}

    descriptor = module.declare_workflow(
        "workflow.async", handler, input_schema={"type": "object"}
    )

    assert descriptor.kind == "workflow"
    assert asyncio.run(module._job_handlers["workflow.async"](_flow(Documents()))) == {
        "ok": True
    }


def test_a_cancelled_step_is_interrupted_after_the_grace_and_frees_its_slot():
    docs, started = Documents(), threading.Event()

    def busy():
        started.set()
        while True:
            sum(range(1000))

    def handler(ctx):
        return ctx.step("busy", busy)

    runner = SyncJobRunner(
        handler, interrupt_grace_seconds=0.2, context_factory=SyncFlowContext
    )

    async def run():
        ctx = _flow(docs)
        task = asyncio.ensure_future(runner(ctx))
        await asyncio.get_running_loop().run_in_executor(None, started.wait, 5)
        begun = time.monotonic()
        ctx.cancelled.set()
        with pytest.raises(JobInterrupted):
            await task
        return time.monotonic() - begun

    assert asyncio.run(run()) < 5
    assert "busy" in docs.statuses()
    assert docs.statuses()["busy"] != "SUCCEEDED"


def test_cancelling_between_steps_raises_workflow_cancelled(host_loop):
    ctx = _sync_ctx(Documents(), host_loop)
    ctx.cancelled.set()

    with pytest.raises(WorkflowCancelled):
        ctx.step("never", lambda: 1)


def test_the_jobs_of_a_class_stay_descriptors_of_the_sdk():
    assert all(isinstance(j, JobDescriptor) for j in _Module.jobs)


def test_a_base_module_declares_sync_workflows_and_hosts_them_like_jobs():
    from naas_abi_core.module.Module import BaseModule, ModuleConfiguration

    class Acme(BaseModule):
        class Configuration(ModuleConfiguration):
            pass

        @workflow()
        def flow(self, ctx: SyncFlowContext, inp: _ReportInput) -> dict:
            return {"n": ctx.step("n", lambda: inp.n)}

    module = object.__new__(Acme)
    handler = as_async_handler(module._job_handlers["flow"], interrupt_grace_seconds=1)

    assert [j.kind for j in Acme.jobs] == ["workflow"]
    assert module.missing_job_handlers() == set()
    assert asyncio.run(handler(_flow(Documents(), payload={"n": 3}))) == {"n": 3}
