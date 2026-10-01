"""Engine module jobs on a real broker; requires a local nats-server (>= 2.14)."""

import asyncio
import json
import shutil
import socket
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    DiscoveryConfiguration,
    NATSConfiguration,
    NATSJobsConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineJobLoader import EngineJobLoader
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.module.jobs import Every, JobsMixin, job
from naas_abi_sdk.jobs import JobDescriptor, JobProxy, runs_collection
from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict
from naas_abi_sdk.services.models import Document
from naas_abi_sdk.transport import Transport

SECRET = "engine-job-integration-secret-32-bytes"
PROJECT = "itest"
pytestmark = pytest.mark.integration


class Documents:
    """Thread-safe in-memory run records (the engine's Document Service is not under test)."""

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

    def runs(self, job_name):
        with self.lock:
            return [
                d.data
                for (c, _), d in self.data.items()
                if c == runs_collection(PROJECT) and d.data.get("job") == job_name
            ]


class _Module(JobsMixin):
    """A core-style module: sync handlers that block, as engine code does."""

    _sync_jobs = True

    @job(triggers=(Every("1s"),))
    def tick(self, ctx):
        time.sleep(0.05)
        return "ticked"

    @job()
    def compact(self, ctx):
        ctx.log("compacting")
        return {
            "dataset": ctx.payload.get("dataset"),
            "thread": threading.current_thread().name,
        }


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


def _wait(predicate, timeout=8.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("condition not met in time")
        time.sleep(0.05)


def test_engine_hosts_scheduled_and_triggered_jobs_of_core_modules(broker):
    docs = Documents()
    loader = EngineJobLoader(
        NATSConfiguration(
            nats_url=broker,
            jwt_secret=SECRET,
            discovery=DiscoveryConfiguration(project=PROJECT),
        ),
        documents_factory=lambda transport, module_id: docs,
        host_options={"fetch_timeout_seconds": 0.2},
    )
    loader.start({"acme.datasets": _Module()}, document_available=True)
    try:
        _wait(lambda: any(r["status"] == "SUCCEEDED" for r in docs.runs("tick")))

        async def trigger():
            transport = Transport(broker, issue_service_token("caller", SECRET))
            try:
                proxy = JobProxy(
                    transport, PROJECT, "acme.datasets", JobDescriptor("compact"), docs
                )
                run = await proxy.trigger({"dataset": "orders"})
                return await run.wait(timeout=8, poll_seconds=0.05)
            finally:
                await transport.close()

        record = asyncio.run(trigger())
    finally:
        loader.stop()

    assert record["status"] == "SUCCEEDED"
    assert record["result"]["dataset"] == "orders"
    assert record["result"]["thread"] != "abi-engine-jobs-loop"
    assert record["logs"] == ["compacting"]
    tick = next(r for r in docs.runs("tick") if r["status"] == "SUCCEEDED")
    assert tick["trigger"]["kind"] == "schedule" and tick["result"] == "ticked"


class _Stubborn(JobsMixin):
    """Busy sync work that never looks at ctx.cancelled."""

    _sync_jobs = True

    def __init__(self):
        self.spans: list[tuple[float, float]] = []
        self.threads: list[threading.Thread] = []
        self.lock = threading.Lock()

    @job(timeout=timedelta(milliseconds=300), max_concurrency=1)
    def crunch(self, ctx):
        start = time.monotonic()
        with self.lock:
            self.threads.append(threading.current_thread())
        try:
            while time.monotonic() - start < float(ctx.payload.get("seconds", 30)):
                sum(range(1000))
            return "finished"
        finally:
            with self.lock:
                self.spans.append((start, time.monotonic()))


def test_timed_out_sync_job_is_interrupted_and_never_overlaps_the_next_run(broker):
    docs = Documents()
    module = _Stubborn()
    loader = EngineJobLoader(
        NATSConfiguration(
            nats_url=broker,
            jwt_secret=SECRET,
            discovery=DiscoveryConfiguration(project=PROJECT),
            jobs=NATSJobsConfiguration(interrupt_grace_seconds=0.2),
        ),
        documents_factory=lambda transport, module_id: docs,
        host_options={"fetch_timeout_seconds": 0.2},
    )
    loader.start({"acme.stubborn": module}, document_available=True)
    try:

        async def trigger_two():
            transport = Transport(broker, issue_service_token("caller", SECRET))
            try:
                proxy = JobProxy(
                    transport, PROJECT, "acme.stubborn", JobDescriptor("crunch"), docs
                )
                stuck = await proxy.trigger({"seconds": 30})
                quick = await proxy.trigger({"seconds": 0.05})
                return (
                    await stuck.wait(timeout=10, poll_seconds=0.05),
                    await quick.wait(timeout=10, poll_seconds=0.05),
                )
            finally:
                await transport.close()

        stuck, quick = asyncio.run(trigger_two())
    finally:
        loader.stop()

    assert stuck["status"] == "TIMED_OUT"
    assert quick["status"] == "SUCCEEDED"
    first, second = sorted(module.spans)
    assert first[1] - first[0] < 5  # interrupted, not run for 30s
    assert first[1] <= second[0]  # the slot was held until the thread exited
    assert not any(t.is_alive() for t in module.threads)
