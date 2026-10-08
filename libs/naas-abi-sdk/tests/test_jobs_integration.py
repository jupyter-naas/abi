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
from datetime import datetime, timedelta, timezone

import pytest
from nats.js.errors import NotFoundError

from naas_abi_sdk.job_host import JobHost, ensure_stream
from naas_abi_sdk.jobs import (
    Cron,
    Every,
    JobDescriptor,
    JobProxy,
    JobRun,
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
        now = datetime.now(timezone.utc)
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
        self, collection, *, where=(), order_by=None, limit=100, cursor=None
    ):
        from naas_abi_sdk.services.models import Page

        def matches(data):
            return all(
                data.get(field) == value if op == "eq" else data.get(field) in value
                for field, op, value in where
            )

        items = [d for (c, _), d in self.data.items() if c == collection]
        return Page([d for d in items if matches(d.data)][:limit], None)

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


def test_triggers_and_events_above_the_broker_limit_reach_the_job(broker):
    # nats-server defaults to a 1 MB max_payload: both payloads are claim checks.
    from naas_abi_sdk.bus import BusClient

    docs = Documents()
    manual = JobDescriptor("big_manual")
    on_event = JobDescriptor("big_event", triggers=(OnEvent("evt.itest.big"),))
    blob = "x" * (3 * 1024 * 1024)

    async def measure(ctx):
        data = ctx.payload.get("data", ctx.payload)
        return {"length": len(data["blob"])}

    async def scenario():
        host = _host(broker, docs, [(manual, measure), (on_event, measure)])
        await host.start()
        try:
            transport = Transport(broker, "t")
            run = await JobProxy(transport, PROJECT, MODULE, manual, docs).trigger(
                {"blob": blob}
            )
            first = await run.wait(timeout=8, poll_seconds=0.05)
            await BusClient(transport).publish(
                "evt.itest", "big", json.dumps({"blob": blob}).encode()
            )
            await _until(
                lambda: any(r["status"] == "SUCCEEDED" for r in docs.runs("big_event"))
            )
            await transport.close()
            return first
        finally:
            await host.close()

    first = asyncio.run(scenario())

    assert first["status"] == "SUCCEEDED" and first["result"] == {"length": len(blob)}
    bridged = next(r for r in docs.runs("big_event") if r["status"] == "SUCCEEDED")
    assert bridged["result"] == {"length": len(blob)}


def test_a_module_triggers_its_own_job_once_per_idempotency_key(broker):
    from naas_abi_sdk.jobs import JobsMixin

    docs = Documents()
    descriptor = JobDescriptor("work")

    class Module(JobsMixin):
        jobs = (descriptor,)

    async def handler(ctx):
        return ctx.payload

    async def scenario():
        host = _host(broker, docs, [(descriptor, handler)])
        await host.start()
        module = Module()
        module._bind_job_host(host, asyncio.get_running_loop())
        try:
            first = await module.atrigger_job("work", {"n": 1}, idempotency_key="req-1")
            again = await module.atrigger_job("work", {"n": 1}, idempotency_key="req-1")
            other = await module.atrigger_job("work", {"n": 2})
            await _until(
                lambda: sum(r["status"] == "SUCCEEDED" for r in docs.runs("work")) >= 2
            )
            await asyncio.sleep(0.3)  # a duplicate would have run by now
            return first, again, other
        finally:
            await host.close()

    first, again, other = asyncio.run(scenario())

    assert first.run_id == again.run_id != other.run_id
    assert sorted(r["payload"]["n"] for r in docs.runs("work")) == [1, 2]


def test_event_filters_and_skipped_runs_on_a_real_broker(broker):
    import nats

    docs = Documents()
    puts = OnEvent("evt.itest.>", filter={"prefix": {"prefix": "naas/"}})
    descriptor = JobDescriptor("on_put", triggers=(puts,))

    async def handler(ctx):
        if ctx.payload["data"]["key"] == "empty.csv":
            ctx.skip("empty dump")

    async def scenario():
        host = _host(broker, docs, [(descriptor, handler)])
        await host.start()
        nc = await nats.connect(broker)
        try:
            for n, (prefix, key) in enumerate(
                [("other/", "a.csv"), ("naas/", "b.csv"), ("naas/", "empty.csv")]
            ):
                await nc.publish(
                    f"evt.itest.ev-{n}",
                    json.dumps({"prefix": prefix, "key": key}).encode(),
                )
            await nc.flush()
            await _until(
                lambda: (
                    sum(bool(r.get("finished_at")) for r in docs.runs("on_put")) >= 2
                )
            )
            await asyncio.sleep(0.3)  # the filtered event would have run by now
        finally:
            await nc.close()
            await host.close()

    asyncio.run(scenario())

    assert sorted(
        (r["payload"]["data"]["key"], r["status"]) for r in docs.runs("on_put")
    ) == [("b.csv", "SUCCEEDED"), ("empty.csv", "SKIPPED")]


@pytest.mark.parametrize("stable_ids", [False, True])
def test_each_event_on_one_subject_reaches_each_modules_job(broker, stable_ids):
    descriptor = JobDescriptor("on_put", triggers=(OnEvent("evt.review.put"),))
    stores = [Documents(), Documents()]

    async def handler(ctx):
        return ctx.payload

    async def scenario():
        hosts = [_host(broker, docs, [(descriptor, handler)]) for docs in stores]
        hosts[1].module_id = "acme.other"
        try:
            for host in hosts:
                await host.start()
            nc = await hosts[0].transport.connect()
            await nc.flush()
            await (await hosts[1].transport.connect()).flush()
            for n in range(2):
                headers = {"Nats-Msg-Id": f"event-{n}"} if stable_ids else None
                await nc.publish(
                    "evt.review.put", json.dumps({"n": n}).encode(), headers=headers
                )
                if stable_ids:
                    await nc.publish(
                        "evt.review.put", json.dumps({"n": n}).encode(), headers=headers
                    )
            await _until(
                lambda: all(
                    len([r for r in docs.runs() if r["status"] == "SUCCEEDED"]) == 2
                    for docs in stores
                )
            )
            await asyncio.sleep(0.2)
        finally:
            for host in hosts:
                await host.close()
                await host.transport.close()

    asyncio.run(scenario())
    for docs in stores:
        assert sorted(r["result"]["data"]["n"] for r in docs.runs()) == [0, 1]


def test_log_store_outage_does_not_redeliver_a_running_job_to_another_replica(broker):
    class FailedLogs(Documents):
        failures = 0

        async def put(self, collection, id, data, **kwargs):
            if data["status"] == "RUNNING" and "logs" in data:
                self.failures += 1
                raise RuntimeError("log store unavailable")
            return await super().put(collection, id, data, **kwargs)

    docs = FailedLogs()
    descriptor = JobDescriptor("slow", max_attempts=3)
    active, peak, executions = 0, 0, 0

    async def handler(ctx):
        nonlocal active, peak, executions
        active += 1
        executions += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.8)
        finally:
            active -= 1
        return "done"

    async def scenario():
        hosts = [
            _host(
                broker,
                docs,
                [(descriptor, handler)],
                instance_id=f"i-{n}",
                heartbeat_seconds=0.03,
                ack_wait_seconds=0.15,
            )
            for n in range(2)
        ]
        try:
            for host in hosts:
                await host.start()
            run = await hosts[0].trigger("slow")
            await run.wait(timeout=8, poll_seconds=0.05)
            await asyncio.sleep(0.3)
        finally:
            for host in hosts:
                await host.close()
                await host.transport.close()

    asyncio.run(scenario())
    assert docs.failures > 0
    assert executions == peak == 1


def test_lost_ack_redelivery_retires_saved_completion_without_running_again(broker):
    docs = Documents()
    descriptor = JobDescriptor("once", max_attempts=3)
    executions = []

    async def handler(ctx):
        executions.append(ctx.run_id)
        return {"answer": 42}

    async def scenario():
        host = _host(
            broker,
            docs,
            [(descriptor, handler)],
            heartbeat_seconds=0.03,
            ack_wait_seconds=0.15,
        )
        original_retire = host._retire
        attempts = []

        async def lose_first_ack(msg, status):
            attempts.append(msg.metadata.num_delivered)
            if len(attempts) == 1:
                raise RuntimeError("ack lost")
            await original_retire(msg, status)

        host._retire = lose_first_ack
        try:
            await host.start()
            run = await host.trigger("once")
            record = await run.wait(timeout=8, poll_seconds=0.05)
            await _until(lambda: len(attempts) >= 2)
            await _until(lambda: not host._tasks)
            info = (
                await (await host.transport.connect())
                .jetstream()
                .consumer_info(
                    stream_name(PROJECT),
                    job_subjects(PROJECT, MODULE, descriptor.name).consumer,
                )
            )
            assert info.num_ack_pending == 0
            assert record["result"] == {"answer": 42}
        finally:
            await host.close()
            await host.transport.close()

    asyncio.run(scenario())
    assert len(executions) == 1


# --- schedules across restarts, expired triggers, recreated streams, store outages -----


def test_restarts_more_frequent_than_the_interval_do_not_stop_an_every_schedule(
    broker,
):
    descriptor = JobDescriptor("tick", triggers=(Every("2s"),))

    async def handler(ctx):
        return None

    async def scenario():
        started = time.monotonic()
        while time.monotonic() - started < 4.5:  # a restart every ~0.7 s
            host = _host(broker, Documents(), [(descriptor, handler)])
            await host.start()
            await asyncio.sleep(0.7)
            await host.close()
            await host.transport.close()
        nc = await Transport(broker, "t").connect()
        try:
            trigger = job_subjects(PROJECT, MODULE, "tick").trigger
            fired = await nc.jetstream().get_last_msg(stream_name(PROJECT), trigger)
            return fired.headers
        finally:
            await nc.close()

    # Republishing the schedule on each start restarted its interval: it never fired.
    assert asyncio.run(scenario())["Abi-Job-Trigger"] == "schedule"


def test_replicas_and_restarts_keep_the_schedule_until_it_changes(broker):
    async def handler(ctx):
        return None

    async def scenario():
        hourly = JobDescriptor("digest", triggers=(Every("1h"),))
        subject = job_subjects(PROJECT, MODULE, "digest").schedule(0)
        nc = await Transport(broker, "t").connect()
        js = nc.jetstream()

        async def schedule():
            return await js.get_last_msg(stream_name(PROJECT), subject)

        try:
            replicas = [
                _host(broker, Documents(), [(hourly, handler)], instance_id=i)
                for i in ("a", "b")
            ]
            await asyncio.gather(*(host.start() for host in replicas))
            first = await schedule()
            for host in replicas:
                await host.close()
            restarted = _host(broker, Documents(), [(hourly, handler)])
            await restarted.start()
            await restarted.close()
            unchanged = await schedule()
            every_two = JobDescriptor("digest", triggers=(Every("2h"),))
            changed_host = _host(broker, Documents(), [(every_two, handler)])
            await changed_host.start()
            await changed_host.close()
            return first, unchanged, await schedule()
        finally:
            await nc.close()

    first, unchanged, changed = asyncio.run(scenario())

    assert unchanged.seq == first.seq
    assert changed.seq > first.seq
    assert changed.headers["Nats-Schedule"] == "@every 2h"


def _publish_trigger(broker, job, ttl):
    async def publish():
        nc = await Transport(broker, "t").connect()
        try:
            ack = await nc.jetstream().publish(
                job_subjects(PROJECT, MODULE, job).trigger,
                b"{}",
                headers={"Abi-Job-Trigger": "manual", "Nats-TTL": ttl},
                stream=stream_name(PROJECT),
            )
            return ack.seq
        finally:
            await nc.close()

    return publish()


def test_a_trigger_expiring_before_its_retry_ends_the_run_failed(broker):
    docs = Documents()
    descriptor = JobDescriptor("slow", max_attempts=2)
    attempts = []

    async def handler(ctx):
        attempts.append(ctx.attempt)
        await asyncio.sleep(3)
        raise RuntimeError("upstream 503")

    async def scenario():
        host = _host(broker, docs, [(descriptor, handler)], backoff_base_seconds=0.2)
        await host.start()
        try:
            sequence = await _publish_trigger(broker, "slow", "2s")
            run = JobRun(
                Transport(broker, "t"),
                PROJECT,
                MODULE,
                "slow",
                f"slow:{sequence}",
                docs,
            )
            return await run.wait(timeout=10, poll_seconds=0.05)
        finally:
            await host.close()
            await host.transport.close()

    record = asyncio.run(scenario())

    assert attempts == [1]
    assert record["status"] == "FAILED"
    assert record["error"].startswith("Trigger expired before it could be retried")


def test_the_reaper_fails_retries_whose_trigger_left_the_stream(broker):
    docs = Documents()
    descriptor = JobDescriptor("sync", max_attempts=3)

    async def handler(ctx):
        return None

    async def scenario():
        host = _host(broker, docs, [(descriptor, handler)])
        # The stream, without consumers taking the triggers.
        await ensure_stream((await host.transport.connect()).jetstream(), PROJECT)
        expiring = await _publish_trigger(broker, "sync", "1s")
        kept = await _publish_trigger(broker, "sync", "1h")
        due = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        for sequence in (expiring, kept):
            await docs.put(
                runs_collection(PROJECT),
                f"sync:{sequence}",
                {
                    "job": "sync",
                    "run_id": f"sync:{sequence}",
                    "status": "RETRYING",
                    "attempt": 1,
                    "max_attempts": 3,
                    "sequence": sequence,
                    "heartbeat_at": due,
                    "retry_at": due,
                },
            )
        await asyncio.sleep(2.5)  # the 1 s trigger expires
        try:
            return expiring, kept, await host.reap_lost_runs()
        finally:
            await host.transport.close()

    expiring, kept, reaped = asyncio.run(scenario())

    assert reaped == 1
    assert {r["run_id"]: r["status"] for r in docs.runs("sync")} == {
        f"sync:{expiring}": "FAILED",
        f"sync:{kept}": "RETRYING",
    }


def test_a_recreated_jobs_stream_runs_triggers_that_reuse_old_sequences(broker):
    docs = Documents()
    descriptor = JobDescriptor("echo")
    executions = []

    async def handler(ctx):
        executions.append(ctx.payload["n"])
        return ctx.payload

    def finished(n):
        return any(
            r["status"] == "SUCCEEDED" and r["result"] == {"n": n}
            for r in docs.runs("echo")
        )

    async def run_once(n):
        host = _host(broker, docs, [(descriptor, handler)])
        await host.start()
        try:
            run = await host.trigger("echo", {"n": n})
            await _until(lambda: finished(n))
            return run.run_id
        finally:
            await host.close()
            await host.transport.close()

    async def scenario():
        first_id = await run_once(1)
        nc = await Transport(broker, "t").connect()
        await nc.jetstream().delete_stream(stream_name(PROJECT))  # lost or recreated
        await nc.close()
        return first_id, await run_once(2)

    first_id, second_id = asyncio.run(scenario())

    assert first_id == second_id  # sequences restarted
    assert executions == [1, 2]


def test_a_store_outage_when_a_trigger_arrives_uses_no_attempt(broker):
    class Outage(Documents):
        failures = 2

        async def get(self, collection, id):
            if self.failures:
                self.failures -= 1
                raise RuntimeError("store unavailable")
            return await super().get(collection, id)

    docs = Outage()
    descriptor = JobDescriptor("fragile")  # a single attempt
    attempts = []

    async def handler(ctx):
        attempts.append(ctx.attempt)
        return "done"

    async def scenario():
        host = _host(broker, docs, [(descriptor, handler)], backoff_base_seconds=0.1)
        await host.start()
        try:
            await host.trigger("fragile")
            await _until(
                lambda: any(r["status"] == "SUCCEEDED" for r in docs.runs("fragile"))
            )
        finally:
            await host.close()
            await host.transport.close()

    asyncio.run(scenario())

    assert docs.failures == 0 and attempts == [1]
    assert docs.runs("fragile")[0]["attempt"] == 1


def test_a_trigger_for_a_new_job_sent_before_its_host_starts_runs_once(broker):
    """A staged generation's consumers exist before it can serve (rollouts)."""
    docs = Documents()
    executions = []

    async def handler(ctx):
        executions.append(ctx.run_id)

    serving_tick = JobDescriptor("tick", triggers=(Every("1h"),))
    staged_tick = JobDescriptor("tick", triggers=(Every("2h"),), max_concurrency=3)
    fresh = JobDescriptor("fresh", triggers=(Every("1h"),))
    tick = job_subjects(PROJECT, MODULE, "tick")

    async def scenario():
        nc = await Transport(broker, "t").connect()
        js = nc.jetstream()
        stream = stream_name(PROJECT)
        caller = Transport(broker, "t")
        serving = _host(broker, docs, [(serving_tick, handler)], instance_id="v1")
        staged = _host(
            broker, docs, [(staged_tick, handler), (fresh, handler)], instance_id="v2"
        )
        try:
            await serving.start()
            schedule = await js.get_last_msg(stream, tick.schedule(0))
            await staged.prepare()
            # The serving generation keeps its schedules and consumer limits.
            assert (await js.get_last_msg(stream, tick.schedule(0))).seq == (
                schedule.seq
            )
            assert (
                await js.consumer_info(stream, tick.consumer)
            ).config.max_ack_pending == 1
            with pytest.raises(NotFoundError):
                await js.get_last_msg(
                    stream, job_subjects(PROJECT, MODULE, "fresh").schedule(0)
                )
            # Cutover: a caller triggers the new job before the new host fetches.
            run = await JobProxy(caller, PROJECT, MODULE, fresh, docs).trigger()
            await asyncio.sleep(0.5)
            assert executions == []  # a prepared host runs nothing
            await staged.start()
            record = await run.wait(timeout=8, poll_seconds=0.05)
            limits = (await js.consumer_info(stream, tick.consumer)).config
            return record, limits.max_ack_pending
        finally:
            for host in (staged, serving):
                await host.close()
                await host.transport.close()
            await caller.close()
            await nc.close()

    record, max_ack_pending = asyncio.run(scenario())

    assert record["status"] == "SUCCEEDED"
    assert executions == [record["run_id"]]
    assert len(docs.runs("fresh")) == 1
    assert max_ack_pending == 3  # start() applies the new generation's limits
