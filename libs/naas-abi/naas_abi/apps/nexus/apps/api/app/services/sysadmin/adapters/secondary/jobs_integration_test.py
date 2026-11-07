"""Jobs end to end on a real nats-server (JetStream): an SDK job host runs the jobs,
NatsJobControl triggers and cancels them, DocumentJobRunStore reads their records
(written to a real SQLite document root), NatsJobQueue reads consumer depth.
The workflow test runs the REST service over the same adapters: start with and
without ``wait``, steps with a child run, a refused input, a cancel."""

import asyncio
import shutil
import socket
import subprocess
import time
from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.document_job_runs import (
    DocumentJobRunStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.document_workflow_steps import (
    DocumentWorkflowSteps,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_resources import (
    InMemoryAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.job_catalogs import (
    EngineJobCatalog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.json_schema_validator import (
    JsonSchemaValidator,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_job_control import (
    NatsJobControl,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_job_queue import (
    NatsJobQueue,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import InvalidInput, RunNotFound
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs_service import JobsAdminService
from naas_abi.apps.nexus.apps.api.app.services.workflows.service import WorkflowsService
from naas_abi.apps.nexus.apps.api.app.services.workflows.workflows import Caller
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.DocumentPort import CollectionSpec, FieldSpec
from naas_abi_core.services.document.DocumentPort import DocumentNotFound as CoreNotFound
from naas_abi_core.services.document.DocumentPort import VersionConflict as CoreConflict
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_sdk.job_host import JobHost
from naas_abi_sdk.jobs import JobDescriptor, JobsMixin
from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict
from naas_abi_sdk.services.models import Document
from naas_abi_sdk.transport import Transport
from naas_abi_sdk.workflows import FlowContext, workflow

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("nats-server") is None, reason="nats-server not installed"),
]

PROJECT, MODULE = "itest", "acme.jobs"


class SdkDocuments:
    """The SDK document API a job host expects, over a core namespace view."""

    def __init__(self, view):
        self.view = view

    async def ensure_collection(self, spec):
        fields = tuple(FieldSpec(name=f.name, type=f.type, indexed=f.indexed) for f in spec.fields)
        self.view.ensure_collection(CollectionSpec(name=spec.name, fields=fields))

    async def find(self, collection, *, where=(), order_by=None, limit=100, cursor=None):
        page = self.view.find(
            collection, where=where, order_by=order_by, limit=limit, cursor=cursor
        )
        items = [Document(d.id, d.data, d.created_at, d.updated_at, d.version) for d in page.items]
        return SimpleNamespace(items=items, cursor=page.cursor)

    async def delete(self, collection, id, *, if_version=None):
        try:
            self.view.delete(collection, id, if_version=if_version)
        except CoreNotFound:
            raise DocumentNotFound("NOT_FOUND", id) from None

    async def get(self, collection, id):
        try:
            doc = self.view.get(collection, id)
        except CoreNotFound:
            raise DocumentNotFound("NOT_FOUND", id) from None
        return Document(doc.id, doc.data, doc.created_at, doc.updated_at, doc.version)

    async def put(self, collection, id, data, *, if_version=None):
        try:
            doc = self.view.put(collection, id, data, if_version=if_version)
        except CoreConflict:
            raise VersionConflict("VERSION_CONFLICT", id) from None
        return Document(doc.id, doc.data, doc.created_at, doc.updated_at, doc.version)


@pytest.fixture
def broker(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    process = subprocess.Popen(
        ["nats-server", "-a", "127.0.0.1", "-p", str(port), "-js", "-sd", str(tmp_path / "js")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.05)
    yield f"nats://127.0.0.1:{port}"
    process.terminate()
    process.wait(timeout=5)


@pytest.fixture
def root(tmp_path):
    return DocumentService._for_engine(
        DocumentSecondaryAdapterSQLite(str(tmp_path / "docs.sqlite"))
    )


async def _until(store, run_id, done, timeout=10.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            run = await store.get_run(MODULE, run_id)
            if done(run):
                return run
        except RunNotFound:
            pass
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"run {run_id} never reached the expected state")
        await asyncio.sleep(0.05)


def test_trigger_record_queue_and_cancel_end_to_end(broker, root):
    async def quick(ctx):
        ctx.log("quick ran")
        return {"echo": ctx.payload}

    async def slow(ctx):
        for _ in range(400):
            if ctx.cancelled.is_set():
                return None
            await asyncio.sleep(0.05)
        return "finished without a cancel"

    async def scenario():
        transport = Transport(broker, "test-token")
        host = JobHost(
            transport,
            SdkDocuments(root.for_namespace(MODULE)),
            MODULE,
            PROJECT,
            {
                "quick": (JobDescriptor("quick"), quick),
                "slow": (JobDescriptor("slow"), slow),
            },
            instance_id="i-1",
            fetch_timeout_seconds=0.2,
            heartbeat_seconds=0.2,
        )
        await host.start()
        control = NatsJobControl(lambda: transport, PROJECT)
        store = DocumentJobRunStore(lambda: root, PROJECT)
        queue = NatsJobQueue(transport.connect, PROJECT)
        try:
            run_id = await control.trigger(MODULE, "quick", {"n": 1})
            done = await _until(store, run_id, lambda r: r.status == "SUCCEEDED")
            assert done.result == {"echo": {"n": 1}}
            assert done.logs == ("quick ran",)
            assert done.trigger.kind == "manual" and done.fired_at and done.duration_ms is not None
            assert done.fired_at <= done.started_at
            assert await queue.depth(MODULE, "quick") == (0, 0)
            assert await queue.depth(MODULE, "never-started") is None

            slow_id = await control.trigger(MODULE, "slow", {})
            await _until(store, slow_id, lambda r: r.status == "RUNNING")
            assert await queue.depth(MODULE, "slow") == (0, 1)
            await control.cancel(MODULE, "slow", slow_id)
            cancelled = await _until(store, slow_id, lambda r: r.status == "CANCELLED")
            assert cancelled.finished_at

            runs = await store.list_runs([MODULE])
            assert [r.run_id for r in runs] == [slow_id, run_id]
        finally:
            await host.close()
            await transport.close()

    asyncio.run(scenario())


class Flows(JobsMixin):
    """``ingest`` fetches, then calls ``double`` for each item; ``slow`` waits to be cancelled."""

    @workflow(
        input_schema={
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 1}},
            "required": ["n"],
        }
    )
    async def ingest(self, ctx: FlowContext, inp: dict) -> dict:
        items = await ctx.step("fetch", self.fetch, inp["n"])
        doubled = await ctx.map_call("double", MODULE, "double", [{"n": i} for i in items])
        return {"total": sum(d["n"] for d in doubled)}

    async def fetch(self, n):
        return list(range(1, n + 1))

    @workflow()
    async def double(self, ctx: FlowContext, inp: dict) -> dict:
        return {"n": inp["n"] * 2}

    @workflow()
    async def slow(self, ctx: FlowContext, inp: dict) -> dict:
        for _ in range(400):
            if ctx.cancelled.is_set():
                return {}
            await asyncio.sleep(0.05)
        return {"finished": True}


def test_a_workflow_is_started_waited_for_followed_step_by_step_and_cancelled(broker, root):
    async def scenario():
        module = Flows()
        docs = SdkDocuments(root.for_namespace(MODULE))
        transport = Transport(broker, "test-token")
        host = JobHost(
            transport,
            docs,
            MODULE,
            PROJECT,
            {j.name: (j, module._job_handlers[j.name]) for j in module.jobs},
            instance_id="i-1",
            fetch_timeout_seconds=0.2,
            heartbeat_seconds=0.2,
            module_documents=lambda module_id: docs,
            workflow_poll_seconds=0.5,
        )
        await host.start()
        audit = InMemoryAuditLog()
        service = WorkflowsService(
            JobsAdminService(
                catalogs=[EngineJobCatalog(lambda: {MODULE: module})],
                runs=DocumentJobRunStore(lambda: root, PROJECT),
                control=NatsJobControl(lambda: transport, PROJECT),
                queue=NatsJobQueue(transport.connect, PROJECT),
                audit=audit,
                project=PROJECT,
                steps=DocumentWorkflowSteps(lambda: root, PROJECT),
                validator=JsonSchemaValidator(),
            )
        )
        caller = Caller("api_key", "u1")
        try:
            listed = (await service.list()).workflows
            ingest = next(w for w in listed if w.name == "ingest")
            assert ingest.kind == "workflow" and ingest.input_schema["required"] == ["n"]

            started = await service.start(caller, MODULE, "ingest", {"n": 3}, wait=10)

            assert started.view.finished and started.view.run.status == "SUCCEEDED"
            assert started.view.run.result == {"total": 12}
            steps = {s.key: s for s in started.view.workflow.steps}
            assert steps["fetch"].status == "SUCCEEDED" and steps["fetch"].child is None
            children = [s.child for s in started.view.workflow.steps if s.child]
            assert sorted(c.workflow for c in children) == ["double"] * 3
            # A child link opens the child's own run, with its result.
            child = await service.status(children[0].module_id, children[0].run_id)
            assert child.run.status == "SUCCEEDED" and "n" in child.run.result

            # Without wait: accepted at once, followed to the end by status.
            quick = await service.start(caller, MODULE, "ingest", {"n": 1})
            assert quick.view.run.status == "QUEUED"
            for _ in range(200):
                if (await service.status(MODULE, quick.run_id)).finished:
                    break
                await asyncio.sleep(0.05)
            assert (await service.status(MODULE, quick.run_id)).run.result == {"total": 2}

            # A refused input starts nothing and leaves no audit record.
            before = len(audit.records)
            with pytest.raises(InvalidInput) as refused:
                await service.start(caller, MODULE, "ingest", {"n": 0})
            assert refused.value.issues[0].path == "/n"
            assert len(audit.records) == before

            slow = await service.start(caller, MODULE, "slow", {})
            for _ in range(200):
                if (await service.status(MODULE, slow.run_id)).run.status == "RUNNING":
                    break
                await asyncio.sleep(0.05)
            await service.cancel(caller, MODULE, slow.run_id)
            for _ in range(200):
                if (await service.status(MODULE, slow.run_id)).finished:
                    break
                await asyncio.sleep(0.05)
            assert (await service.status(MODULE, slow.run_id)).run.status == "CANCELLED"

            assert {(r.action.via, r.action.actor_id) for r in audit.records} == {("api_key", "u1")}
            assert [r.action.operation for r in audit.records].count("cancel") == 2
        finally:
            await host.close()
            await transport.close()

    asyncio.run(scenario())
