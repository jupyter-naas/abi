"""Jobs end to end on a real nats-server (JetStream): an SDK job host runs the jobs,
NatsJobControl triggers and cancels them, DocumentJobRunStore reads their records
(written to a real SQLite document root), NatsJobQueue reads consumer depth."""

import asyncio
import shutil
import socket
import subprocess
import time

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.document_job_runs import (
    DocumentJobRunStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_job_control import (
    NatsJobControl,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_job_queue import (
    NatsJobQueue,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import RunNotFound
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.DocumentPort import CollectionSpec
from naas_abi_core.services.document.DocumentPort import DocumentNotFound as CoreNotFound
from naas_abi_core.services.document.DocumentPort import VersionConflict as CoreConflict
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_sdk.job_host import JobHost
from naas_abi_sdk.jobs import JobDescriptor
from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict
from naas_abi_sdk.services.models import Document
from naas_abi_sdk.transport import Transport

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
        self.view.ensure_collection(CollectionSpec(name=spec.name))

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
