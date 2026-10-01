import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from naas_abi_sdk.job_host import JobHost
from naas_abi_sdk.jobs import (
    TRIGGER_HEADER,
    Cron,
    Every,
    JobDescriptor,
    OnEvent,
    job_subjects,
    runs_collection,
)
from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict
from naas_abi_sdk.services.models import Document

PROJECT, MODULE = "zen", "acme.jobs"


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

    def run(self, run_id):
        return self.data[(runs_collection(PROJECT), run_id)].data


class Msg:
    def __init__(self, sequence=7, attempt=1, payload=None, trigger="manual"):
        self.data = json.dumps(payload or {}).encode()
        self.headers = {TRIGGER_HEADER: trigger}
        self.metadata = SimpleNamespace(
            sequence=SimpleNamespace(stream=sequence), num_delivered=attempt
        )
        self.calls: list[tuple] = []

    async def ack(self):
        self.calls.append(("ack",))

    async def nak(self, delay=None):
        self.calls.append(("nak", delay))

    async def term(self):
        self.calls.append(("term",))

    async def in_progress(self):
        self.calls.append(("in_progress",))


def _host(documents=None, **kwargs):
    return JobHost(
        transport=None,
        documents=documents or Documents(),
        module_id=MODULE,
        project=PROJECT,
        handlers={},
        instance_id="i-1",
        **kwargs,
    )


def _run(host, descriptor, handler, msg):
    asyncio.run(host.handle(descriptor, handler, msg))


def test_success_records_result_logs_and_acks():
    docs = Documents()

    async def handler(ctx):
        ctx.log(f"payload {ctx.payload}")
        return {"rows": 3}

    msg = Msg(payload={"since": "2026-09-01"})
    _run(_host(docs), JobDescriptor("ingest"), handler, msg)

    run = docs.run("ingest:7")
    assert run["status"] == "SUCCEEDED"
    assert run["result"] == {"rows": 3}
    assert run["logs"] == ["payload {'since': '2026-09-01'}"]
    assert run["attempt"] == 1 and run["trigger"]["kind"] == "manual"
    assert msg.calls == [("ack",)]


def test_failure_with_attempts_left_naks_with_backoff():
    docs = Documents()

    async def handler(ctx):
        raise RuntimeError("upstream 503")

    msg = Msg(attempt=1)
    _run(
        _host(docs, backoff_base_seconds=5),
        JobDescriptor("ingest", max_attempts=3),
        handler,
        msg,
    )

    run = docs.run("ingest:7")
    assert run["status"] == "RETRYING"
    assert "upstream 503" in run["error"]
    assert msg.calls == [("nak", 5)]


def test_last_attempt_failure_terminates():
    docs = Documents()

    async def handler(ctx):
        raise RuntimeError("still down")

    msg = Msg(attempt=3)
    _run(_host(docs), JobDescriptor("ingest", max_attempts=3), handler, msg)

    assert docs.run("ingest:7")["status"] == "FAILED"
    assert msg.calls == [("term",)]


def test_timeout_is_reported_and_terminated_without_attempts_left():
    docs = Documents()

    async def handler(ctx):
        await asyncio.sleep(10)

    msg = Msg()
    _run(
        _host(docs),
        JobDescriptor("slow", timeout=timedelta(milliseconds=50)),
        handler,
        msg,
    )

    assert docs.run("slow:7")["status"] == "TIMED_OUT"
    assert msg.calls[-1] == ("term",)


def test_cancel_stops_the_running_job():
    docs = Documents()
    host = _host(docs)
    started = asyncio.Event()

    async def handler(ctx):
        started.set()
        await ctx.cancelled.wait()
        return "stopped"

    async def scenario():
        msg = Msg()
        task = asyncio.create_task(host.handle(JobDescriptor("long"), handler, msg))
        await started.wait()
        assert host.cancel("long:7") is True
        await task
        return msg

    msg = asyncio.run(scenario())

    assert docs.run("long:7")["status"] == "CANCELLED"
    assert msg.calls[-1] == ("ack",)
    assert host.cancel("long:7") is False


def test_long_runs_send_heartbeats():
    async def handler(ctx):
        await asyncio.sleep(0.12)

    msg = Msg()
    _run(_host(heartbeat_seconds=0.03), JobDescriptor("long"), handler, msg)

    assert msg.calls.count(("in_progress",)) >= 2
    assert msg.calls[-1] == ("ack",)


def test_redelivery_updates_the_same_run():
    docs = Documents()
    attempts = []

    async def handler(ctx):
        attempts.append(ctx.attempt)
        if ctx.attempt == 1:
            raise RuntimeError("flaky")

    host = _host(docs)
    descriptor = JobDescriptor("flaky", max_attempts=2)
    _run(host, descriptor, handler, Msg(attempt=1))
    _run(host, descriptor, handler, Msg(attempt=2))

    run = docs.run("flaky:7")
    assert attempts == [1, 2]
    assert run["status"] == "SUCCEEDED" and run["attempt"] == 2


class JetStream:
    def __init__(self):
        self.published: list[tuple[str, bytes, dict]] = []
        self.purged: list[str] = []

    async def publish(self, subject, payload=b"", headers=None, stream=None):
        self.published.append((subject, payload, dict(headers or {})))
        return SimpleNamespace(seq=len(self.published))

    async def purge_stream(self, name, subject=None):
        self.purged.append(subject)


def test_schedules_follow_the_declared_triggers():
    js = JetStream()
    descriptor = JobDescriptor(
        "ingest",
        triggers=(
            Cron("0 0 6 * * *", time_zone="Europe/Paris"),
            Every("1h"),
            OnEvent(subject="evt.x.>"),
        ),
    )

    asyncio.run(_host().reconcile_schedules(js, descriptor))

    subjects = job_subjects(PROJECT, MODULE, "ingest")
    assert [p[0] for p in js.published] == [subjects.schedule(0), subjects.schedule(1)]
    first = js.published[0][2]
    assert first["Nats-Schedule"] == "0 0 6 * * *"
    assert first["Nats-Schedule-Time-Zone"] == "Europe/Paris"
    assert first["Nats-Schedule-Target"] == subjects.trigger
    assert first[TRIGGER_HEADER] == "schedule"
    assert first["Nats-Schedule-TTL"] == "3600s"  # unprocessed ticks expire
    assert js.published[1][2]["Nats-Schedule"] == "@every 1h"
    assert js.purged == [subjects.schedule(i) for i in range(2, 16)]


def test_event_bridge_turns_an_event_into_a_trigger():
    js = JetStream()
    event = SimpleNamespace(
        subject="evt.abc.ev-42", data=json.dumps({"key": "a.csv"}).encode()
    )

    asyncio.run(
        _host().bridge_event(
            js, JobDescriptor("on_put", triggers=(OnEvent("evt.abc.>"),)), event
        )
    )

    subject, payload, headers = js.published[0]
    assert subject == job_subjects(PROJECT, MODULE, "on_put").trigger
    assert json.loads(payload) == {"subject": "evt.abc.ev-42", "data": {"key": "a.csv"}}
    assert headers == {
        TRIGGER_HEADER: "event",
        "Nats-Msg-Id": "on_put:evt.abc.ev-42",
        "Nats-TTL": "24h",
    }


def _closing_scenario(handler, **kwargs):
    docs = Documents()
    host = _host(docs, close_grace_seconds=0.05, **kwargs)
    started = asyncio.Event()

    async def wrapped(ctx):
        started.set()
        return await handler(ctx)

    async def scenario():
        msg = Msg()
        host._spawn(host.handle(JobDescriptor("long", max_attempts=3), wrapped, msg))
        await started.wait()
        await host.close()
        return msg

    msg = asyncio.run(scenario())
    return docs.run("long:7"), msg


def test_shutdown_is_not_a_user_cancel_the_run_is_retried():
    async def cooperative(ctx):
        await ctx.cancelled.wait()
        return "stopped"

    run, msg = _closing_scenario(cooperative)

    assert run["status"] == "RETRYING"
    assert run["error"] == "Interrupted by host shutdown"
    assert msg.calls[-1][0] == "nak"


def test_close_cancels_jobs_still_running_after_the_grace_period():
    async def stubborn(ctx):
        await asyncio.sleep(
            30
        )  # ignores ctx.cancelled; only task cancellation stops it

    run, msg = _closing_scenario(stubborn, close_cancel_seconds=1)

    assert run["status"] == "RETRYING"
    assert run["error"] == "Interrupted by host shutdown"
    assert msg.calls[-1][0] == "nak"
