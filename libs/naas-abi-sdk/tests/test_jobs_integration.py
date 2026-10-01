"""Jobs against a real nats-server (>= 2.14): schedules, consumers, retries, replicas.

Skipped when ``nats-server`` is not on PATH. Run records use an in-memory store;
everything NATS-side (stream, schedules, consumers, acks) is real.
"""

import asyncio
import contextlib
import itertools
import json
import shutil
import socket
import subprocess
import time
from datetime import UTC, datetime, timedelta

import pytest
from nats.js.errors import NotFoundError

from naas_abi_sdk.job_host import JobHost
from naas_abi_sdk.jobs import (
    Cron,
    Every,
    JobDescriptor,
    JobProxy,
    OnEvent,
    job_subjects,
    runs_collection,
    stream_name,
)
from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict
from naas_abi_sdk.services.models import Document
from naas_abi_sdk.transport import Transport

pytestmark = pytest.mark.skipif(
    shutil.which("nats-server") is None, reason="nats-server not installed"
)

PROJECT, MODULE = "itest", "acme.jobs"


class Documents:
    def __init__(self):
        self.data: dict[tuple[str, str], Document] = {}

    async def ensure_collection(self, spec):
        return None

    async def get(self, collection, id):
        try:
            return self.data[(collection, id)]
        except KeyError:
            raise DocumentNotFound("NOT_FOUND", id) from None

    async def put(self, collection, id, data, *, if_version=None):
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

    def runs(self, job=None):
        return [
            d.data
            for (c, _), d in self.data.items()
            if c == runs_collection(PROJECT)
            and (job is None or d.data.get("job") == job)
        ]


@pytest.fixture
def broker(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    process = subprocess.Popen(
        [
            "nats-server",
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


def _host(url, documents, jobs, **kwargs):
    return JobHost(
        Transport(url, "test-token"),
        documents,
        MODULE,
        PROJECT,
        {d.name: (d, h) for d, h in jobs},
        instance_id=kwargs.pop("instance_id", "i-1"),
        fetch_timeout_seconds=0.2,
        **kwargs,
    )


async def _until(predicate, timeout=8.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.05)


def test_manual_trigger_runs_once_and_reports(broker):
    docs = Documents()
    descriptor = JobDescriptor("echo")

    async def handler(ctx):
        ctx.log("hello")
        return {"echo": ctx.payload}

    async def scenario():
        host = _host(broker, docs, [(descriptor, handler)])
        await host.start()
        try:
            run = await JobProxy(
                Transport(broker, "t"), PROJECT, MODULE, descriptor, docs
            ).trigger({"x": 1})
            return await run.wait(timeout=8, poll_seconds=0.05)
        finally:
            await host.close()

    record = asyncio.run(scenario())

    assert record["status"] == "SUCCEEDED"
    assert record["result"] == {"echo": {"x": 1}}
    assert record["logs"] == ["hello"] and record["trigger"]["kind"] == "manual"
    assert len(docs.runs("echo")) == 1


def test_every_schedule_fires_repeatedly(broker):
    docs = Documents()

    async def handler(ctx):
        return None

    async def scenario():
        host = _host(
            broker, docs, [(JobDescriptor("tick", triggers=(Every("1s"),)), handler)]
        )
        await host.start()
        try:
            await _until(lambda: len(docs.runs("tick")) >= 2)
        finally:
            await host.close()

    asyncio.run(scenario())

    runs = docs.runs("tick")
    assert all(r["trigger"]["kind"] == "schedule" for r in runs)
    assert all(r["status"] == "SUCCEEDED" for r in runs if r["status"] != "RUNNING")


def test_cron_with_time_zone_is_accepted_and_fires(broker):
    docs = Documents()

    async def handler(ctx):
        return None

    async def scenario():
        descriptor = JobDescriptor(
            "every_second", triggers=(Cron("* * * * * *", time_zone="Europe/Paris"),)
        )
        host = _host(broker, docs, [(descriptor, handler)])
        await host.start()
        try:
            await _until(lambda: len(docs.runs("every_second")) >= 1)
        finally:
            await host.close()

    asyncio.run(scenario())


def test_max_concurrency_one_never_overlaps(broker):
    docs = Documents()
    spans: list[tuple[float, float]] = []
    descriptor = JobDescriptor("serial", max_concurrency=1)

    async def handler(ctx):
        start = time.monotonic()
        await asyncio.sleep(0.3)
        spans.append((start, time.monotonic()))

    async def scenario():
        host = _host(broker, docs, [(descriptor, handler)])
        await host.start()
        try:
            proxy = JobProxy(Transport(broker, "t"), PROJECT, MODULE, descriptor, docs)
            runs = [await proxy.trigger() for _ in range(3)]
            for run in runs:
                await run.wait(timeout=8, poll_seconds=0.05)
        finally:
            await host.close()

    asyncio.run(scenario())

    spans.sort()
    assert len(spans) == 3
    assert all(
        previous[1] <= current[0] for previous, current in itertools.pairwise(spans)
    )


def test_failure_is_retried_with_backoff_then_succeeds(broker):
    docs = Documents()
    attempts: list[int] = []
    descriptor = JobDescriptor("flaky", max_attempts=3)

    async def handler(ctx):
        attempts.append(ctx.attempt)
        if ctx.attempt == 1:
            raise RuntimeError("first try fails")
        return "ok"

    async def scenario():
        host = _host(broker, docs, [(descriptor, handler)], backoff_base_seconds=0.2)
        await host.start()
        try:
            run = await JobProxy(
                Transport(broker, "t"), PROJECT, MODULE, descriptor, docs
            ).trigger()
            return await run.wait(timeout=8, poll_seconds=0.05)
        finally:
            await host.close()

    record = asyncio.run(scenario())

    assert attempts == [1, 2]
    assert record["status"] == "SUCCEEDED" and record["attempt"] == 2


def test_replicas_share_triggers_without_duplicates(broker):
    docs = Documents()
    seen: list[tuple[str, str]] = []
    descriptor = JobDescriptor("shared", max_concurrency=4)

    def handler_for(instance):
        async def handler(ctx):
            seen.append((instance, ctx.run_id))
            await asyncio.sleep(0.05)

        return handler

    async def scenario():
        hosts = [
            _host(broker, docs, [(descriptor, handler_for(i))], instance_id=i)
            for i in ("a", "b")
        ]
        for host in hosts:
            await host.start()
        try:
            proxy = JobProxy(Transport(broker, "t"), PROJECT, MODULE, descriptor, docs)
            runs = [await proxy.trigger() for _ in range(6)]
            for run in runs:
                await run.wait(timeout=8, poll_seconds=0.05)
        finally:
            for host in hosts:
                await host.close()

    asyncio.run(scenario())

    run_ids = [run_id for _, run_id in seen]
    assert len(run_ids) == 6 and len(set(run_ids)) == 6


def test_events_trigger_runs(broker):
    docs = Documents()
    descriptor = JobDescriptor("on_put", triggers=(OnEvent("evt.itest.>"),))

    async def handler(ctx):
        return ctx.payload

    async def scenario():
        host = _host(broker, docs, [(descriptor, handler)])
        await host.start()
        try:
            nc = await Transport(broker, "t").connect()
            await nc.publish("evt.itest.e-1", json.dumps({"key": "a.csv"}).encode())
            await _until(
                lambda: any(r["status"] == "SUCCEEDED" for r in docs.runs("on_put"))
            )
        finally:
            await host.close()

    asyncio.run(scenario())

    record = next(r for r in docs.runs("on_put") if r["status"] == "SUCCEEDED")
    assert record["trigger"]["kind"] == "event"
    assert record["result"] == {"subject": "evt.itest.e-1", "data": {"key": "a.csv"}}


def test_restart_with_fewer_triggers_purges_the_stale_schedule(broker):
    async def handler(ctx):
        return None

    async def schedules_on(js, descriptor):
        subjects = job_subjects(PROJECT, MODULE, descriptor.name)
        found = []
        for index in range(3):
            with contextlib.suppress(NotFoundError):
                await js.get_last_msg(stream_name(PROJECT), subjects.schedule(index))
                found.append(index)
        return found

    async def scenario():
        two = JobDescriptor(
            "daily", triggers=(Cron("0 0 6 * * *"), Cron("0 0 18 * * *"))
        )
        one = JobDescriptor("daily", triggers=(Cron("0 0 6 * * *"),))
        nc = await Transport(broker, "t").connect()
        js = nc.jetstream()
        host = _host(broker, Documents(), [(two, handler)])
        await host.start()
        await host.close()
        before = await schedules_on(js, two)
        host = _host(broker, Documents(), [(one, handler)])
        await host.start()
        await host.close()
        return before, await schedules_on(js, one)

    before, after = asyncio.run(scenario())

    assert before == [0, 1]
    assert after == [0]


def test_long_timeout_is_not_hit_by_fast_jobs(broker):
    docs = Documents()
    descriptor = JobDescriptor("quick", timeout=timedelta(seconds=5))

    async def handler(ctx):
        return "fast"

    async def scenario():
        host = _host(broker, docs, [(descriptor, handler)])
        await host.start()
        try:
            run = await JobProxy(
                Transport(broker, "t"), PROJECT, MODULE, descriptor, docs
            ).trigger()
            return await run.wait(timeout=8, poll_seconds=0.05)
        finally:
            await host.close()

    assert asyncio.run(scenario())["status"] == "SUCCEEDED"
