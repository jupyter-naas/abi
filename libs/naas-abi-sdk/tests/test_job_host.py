import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

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


class _Connection:
    """Enough of a broker connection to size messages (claim checks)."""

    max_payload = 1024 * 1024


class _Transport:
    async def connect(self):
        return _Connection()


def _host(documents=None, **kwargs):
    return JobHost(
        transport=_Transport(),
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


def test_a_run_continues_the_trace_of_its_trigger(monkeypatch):
    pytest = __import__("pytest")
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from opentelemetry.trace import SpanKind, StatusCode

    from naas_abi_sdk import telemetry

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "_tracer", lambda: provider.get_tracer("test"))

    trigger_headers = {}
    with telemetry.client_span(
        job_subjects(PROJECT, MODULE, "ingest").trigger, trigger_headers
    ):
        pass

    async def failing(ctx):
        raise RuntimeError("upstream 503")

    msg = Msg()
    msg.headers = {**msg.headers, **trigger_headers}
    msg.subject = job_subjects(PROJECT, MODULE, "ingest").trigger
    _run(_host(), JobDescriptor("ingest"), failing, msg)

    trigger, run = exporter.get_finished_spans()
    assert run.name == "job ingest" and run.kind is SpanKind.CONSUMER
    assert run.context.trace_id == trigger.context.trace_id
    assert run.attributes["abi.job.run_id"] == "ingest:7"
    assert run.status.status_code is StatusCode.ERROR


def test_manual_triggers_carry_the_callers_trace(monkeypatch):
    from naas_abi_sdk.jobs import JobProxy

    published = []

    class _JS:
        async def publish(self, subject, payload, headers=None, stream=None):
            published.append(dict(headers or {}))
            return SimpleNamespace(seq=3)

    class _NC:
        max_payload = 1024 * 1024

        def jetstream(self):
            return _JS()

    class _Transport:
        async def connect(self):
            return _NC()

    monkeypatch.setattr(
        "naas_abi_sdk.jobs.client_span",
        lambda subject, headers: _inject(headers),
    )
    asyncio.run(
        JobProxy(_Transport(), PROJECT, MODULE, JobDescriptor("ingest")).trigger({})
    )

    assert published[0]["traceparent"] == "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
    assert published[0][TRIGGER_HEADER] == "manual"


def _inject(headers):
    import contextlib

    headers["traceparent"] = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
    return contextlib.nullcontext()


def test_a_run_records_when_its_trigger_fired():
    docs = Documents()
    fired = datetime(2026, 10, 2, 6, 0, 0, tzinfo=timezone.utc)

    async def handler(ctx):
        return None

    msg = Msg(trigger="schedule")
    msg.metadata.timestamp = fired
    _run(_host(docs), JobDescriptor("ingest"), handler, msg)

    run = docs.run("ingest:7")
    assert run["fired_at"] == fired.isoformat()
    assert run["trace_id"] == ""  # no tracer configured


def test_fired_at_falls_back_to_now_without_a_message_timestamp():
    docs = Documents()

    async def handler(ctx):
        return None

    before = datetime.now(timezone.utc)
    _run(_host(docs), JobDescriptor("ingest"), handler, Msg())

    fired_at = datetime.fromisoformat(docs.run("ingest:7")["fired_at"])
    assert before <= fired_at <= datetime.now(timezone.utc)


def test_a_run_records_the_trace_of_its_consumer_span(monkeypatch):
    pytest = __import__("pytest")
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from naas_abi_sdk import telemetry

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry, "_tracer", lambda: provider.get_tracer("test"))
    docs = Documents()

    async def handler(ctx):
        return None

    msg = Msg()
    msg.subject = job_subjects(PROJECT, MODULE, "ingest").trigger
    _run(_host(docs), JobDescriptor("ingest"), handler, msg)

    (span,) = exporter.get_finished_spans()
    assert docs.run("ingest:7")["trace_id"] == format(span.context.trace_id, "032x")


# --- skipped runs, self-triggers, event filters, retention ------------------------------


def test_a_skipped_run_is_recorded_as_skipped_and_acked():
    docs = Documents()

    async def handler(ctx):
        ctx.skip("no new dumps")
        return {"checked": 2}

    msg = Msg()
    _run(_host(docs), JobDescriptor("ingest"), handler, msg)

    run = docs.run("ingest:7")
    assert run["status"] == "SKIPPED" and run["skip_reason"] == "no new dumps"
    assert run["result"] == {"checked": 2} and run["finished_at"]
    assert msg.calls == [("ack",)]


class _DedupJetStream:
    """Publishes like JetStream with message-id dedup: a repeated id answers the
    first message's sequence with duplicate=True."""

    def __init__(self):
        self.published: list[tuple[str, dict]] = []
        self.ids: dict[str, int] = {}

    async def publish(self, subject, payload=b"", headers=None, stream=None):
        headers = dict(headers or {})
        msg_id = headers.get("Nats-Msg-Id")
        if msg_id in self.ids:
            return SimpleNamespace(seq=self.ids[msg_id], duplicate=True)
        self.published.append((subject, headers))
        if msg_id:
            self.ids[msg_id] = len(self.published)
        return SimpleNamespace(seq=len(self.published), duplicate=False)


def _publishing_host(js, docs=None):
    class _NC:
        max_payload = 1024 * 1024

        def jetstream(self):
            return js

    class _T:
        async def connect(self):
            return _NC()

    async def handler(ctx):
        return None

    return JobHost(
        _T(),
        docs or Documents(),
        MODULE,
        PROJECT,
        {"ingest": (JobDescriptor("ingest"), handler)},
        instance_id="i-1",
    )


def test_a_host_triggers_its_own_jobs_once_per_idempotency_key():
    import pytest

    js = _DedupJetStream()
    host = _publishing_host(js)

    async def scenario():
        first = await host.trigger("ingest", {"run": "r1"}, idempotency_key="r1")
        again = await host.trigger("ingest", {"run": "r1"}, idempotency_key="r1")
        other = await host.trigger("ingest")
        return first, again, other

    first, again, other = asyncio.run(scenario())

    assert first.run_id == again.run_id == "ingest:1" and other.run_id == "ingest:2"
    assert len(js.published) == 2
    subject, headers = js.published[0]
    assert subject == job_subjects(PROJECT, MODULE, "ingest").trigger
    assert bool(headers["Nats-Msg-Id"]) and headers[TRIGGER_HEADER] == "manual"
    assert "Nats-Msg-Id" not in js.published[1][1]
    with pytest.raises(ValueError):
        asyncio.run(host.trigger("someone_elses_job"))


def test_an_event_filter_keeps_irrelevant_events_from_triggering():
    js = JetStream()
    puts = OnEvent("evt.abc.>", filter={"prefix": {"prefix": "naas/"}})
    descriptor = JobDescriptor("on_put", triggers=(puts,))

    def event(prefix, event_id):
        return SimpleNamespace(
            subject=f"evt.abc.{event_id}",
            data=json.dumps({"prefix": prefix, "key": "a.csv"}).encode(),
        )

    async def scenario():
        host = _host()
        await host.bridge_event(js, descriptor, event("other/", "ev-1"), puts)
        await host.bridge_event(js, descriptor, event("naas/mercury", "ev-2"), puts)

    asyncio.run(scenario())

    assert [json.loads(p)["subject"] for _, p, _ in js.published] == ["evt.abc.ev-2"]


class QueryDocuments(Documents):
    """Documents with the queries retention uses: find (eq, in, lt; order_by;
    limit), count and delete."""

    @staticmethod
    def _matches(data, where):
        for field, op, value in where:
            actual = data.get(field)
            if op == "eq" and actual != value:
                return False
            if op == "in" and actual not in value:
                return False
            if op == "lt" and not (actual is not None and actual < value):
                return False
        return True

    def _select(self, collection, where):
        return [
            d
            for (c, _), d in self.data.items()
            if c == collection and self._matches(d.data, where)
        ]

    async def find(
        self, collection, *, where=(), order_by=None, limit=100, cursor=None
    ):
        from naas_abi_sdk.services.models import Page

        items = self._select(collection, where)
        if order_by:
            field, direction = order_by
            items.sort(
                key=lambda d: d.data.get(field) or "", reverse=direction == "desc"
            )
        return Page(items[:limit], None)

    async def count(self, collection, where=()):
        return len(self._select(collection, where))

    async def delete(self, collection, id, *, if_version=None):
        current = self.data.get((collection, id))
        if current is None:
            raise DocumentNotFound("NOT_FOUND", id)
        if if_version is not None and current.version != if_version:
            raise VersionConflict("VERSION_CONFLICT", id)
        del self.data[(collection, id)]

    def ids(self):
        return sorted(i for (c, i) in self.data if c == runs_collection(PROJECT))


def _seed(docs, job, n, status, finished_at):
    run_id = f"{job}:{n}"
    docs.data[(runs_collection(PROJECT), run_id)] = Document(
        id=run_id,
        data={
            "job": job,
            "run_id": run_id,
            "status": status,
            **({"finished_at": finished_at.isoformat()} if finished_at else {}),
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )


def test_retention_drops_old_and_excess_finished_runs_never_active_ones():
    from naas_abi_sdk.jobs import JobRetention

    docs = QueryDocuments()
    now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    _seed(docs, "ingest", 1, "SUCCEEDED", now - timedelta(days=8))  # too old
    _seed(docs, "ingest", 2, "FAILED", now - timedelta(days=1))
    _seed(docs, "ingest", 3, "SKIPPED", now - timedelta(hours=2))  # skipped, stale
    _seed(docs, "ingest", 4, "SKIPPED", now - timedelta(minutes=10))
    _seed(docs, "ingest", 5, "RUNNING", None)  # active: never touched
    _seed(docs, "ingest", 6, "RETRYING", None)
    for n in range(10, 15):  # 5 recent finished runs of another job, cap 3
        _seed(docs, "digest", n, "SUCCEEDED", now - timedelta(minutes=60 - n))
    retention = JobRetention(
        max_age=timedelta(days=7),
        skipped_max_age=timedelta(hours=1),
        max_runs_per_job=3,
    )
    host = JobHost(
        _Transport(),
        docs,
        MODULE,
        PROJECT,
        {
            "ingest": (JobDescriptor("ingest"), None),
            "digest": (JobDescriptor("digest"), None),
        },
        retention=retention,
    )

    deleted = asyncio.run(host.prune(now=now))

    assert docs.ids() == sorted(
        [
            "ingest:2",
            "ingest:4",
            "ingest:5",
            "ingest:6",
            "digest:12",
            "digest:13",
            "digest:14",
        ]
    )
    assert deleted == 4


def test_retention_work_per_pass_is_bounded():
    from naas_abi_sdk.jobs import JobRetention

    docs = QueryDocuments()
    now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    for n in range(25):
        _seed(docs, "tick", n, "SKIPPED", now - timedelta(days=1))
    host = JobHost(
        _Transport(),
        docs,
        MODULE,
        PROJECT,
        {"tick": (JobDescriptor("tick"), None)},
        retention=JobRetention(batch=10),
    )

    assert asyncio.run(host.prune(now=now)) == 10
    assert asyncio.run(host.prune(now=now)) == 10
    assert asyncio.run(host.prune(now=now)) == 5
    assert docs.ids() == []


def test_a_run_records_its_heartbeats():
    docs = Documents()

    async def handler(ctx):
        await asyncio.sleep(0.12)

    _run(_host(docs, heartbeat_seconds=0.03), JobDescriptor("long"), handler, Msg())

    run = docs.run("long:7")
    assert run["heartbeat_at"] > run["started_at"]


def _seed_running(
    docs, n, last_seen, *, attempt=1, max_attempts=1, field="heartbeat_at"
):
    run_id = f"sync:{n}"
    docs.data[(runs_collection(PROJECT), run_id)] = Document(
        id=run_id,
        data={
            "job": "sync",
            "run_id": run_id,
            "status": "RUNNING",
            "attempt": attempt,
            "max_attempts": max_attempts,
            "started_at": last_seen.isoformat(),
            field: last_seen.isoformat(),
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        version=1,
    )


def test_a_run_lost_with_its_host_on_its_last_attempt_is_failed():
    docs = QueryDocuments()
    now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    _seed_running(docs, 1, now - timedelta(minutes=30))  # lost: nothing redelivers it
    _seed_running(docs, 2, now - timedelta(minutes=1))  # alive elsewhere
    # Attempts left: JetStream redelivers it, the next attempt updates the record.
    _seed_running(docs, 3, now - timedelta(minutes=30), max_attempts=3)
    # Recorded before heartbeats were: its start time is its last sign of life.
    _seed_running(docs, 4, now - timedelta(minutes=30), field="started_at")
    _seed_running(docs, 5, now - timedelta(minutes=30))  # running on this host
    host = JobHost(
        _Transport(),
        docs,
        MODULE,
        PROJECT,
        {"sync": (JobDescriptor("sync"), None)},
        lost_after_seconds=300,
    )
    host._running["sync:5"] = object()

    assert asyncio.run(host.reap_lost_runs(now=now)) == 2

    for lost in ("sync:1", "sync:4"):
        run = docs.run(lost)
        assert run["status"] == "FAILED"
        assert run["finished_at"] == now.isoformat()
        assert "no heartbeat since" in run["error"]
    for alive in ("sync:2", "sync:3", "sync:5"):
        assert docs.run(alive)["status"] == "RUNNING"


def test_a_lost_run_updated_meanwhile_is_left_alone():
    docs = QueryDocuments()
    now = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)
    _seed_running(docs, 1, now - timedelta(minutes=30))
    host = JobHost(
        _Transport(), docs, MODULE, PROJECT, {"sync": (JobDescriptor("sync"), None)}
    )
    original_find = docs.find

    async def find_then_heartbeat(*args, **kwargs):
        page = await original_find(*args, **kwargs)
        # Its host sends a heartbeat between the read and the write.
        await docs.put(
            runs_collection(PROJECT),
            "sync:1",
            {**docs.run("sync:1"), "heartbeat_at": now.isoformat()},
        )
        return page

    docs.find = find_then_heartbeat

    assert asyncio.run(host.reap_lost_runs(now=now)) == 0
    assert docs.run("sync:1")["status"] == "RUNNING"


@pytest.mark.parametrize("event_ids", [None, ("event-1", "event-2")])
def test_event_dedup_is_scoped_to_modules_and_individual_events(event_ids):
    js = _DedupJetStream()
    hosts = [_host(), _host()]
    hosts[1].module_id = "acme.other"

    async def scenario():
        for host in hosts:
            for n in range(2):
                msg = SimpleNamespace(
                    subject="evt.review.put",
                    data=json.dumps({"n": n}).encode(),
                    headers={"Nats-Msg-Id": event_ids[n]} if event_ids else {},
                )
                await host.bridge_event(js, JobDescriptor("on_put"), msg)
                if event_ids:
                    await host.bridge_event(js, JobDescriptor("on_put"), msg)

    asyncio.run(scenario())
    assert len(js.published) == 4


@pytest.mark.parametrize("blocked", [False, True])
def test_progress_write_failure_does_not_stop_acknowledgement_renewal(blocked, caplog):
    class FailingProgress(Documents):
        async def put(self, collection, id, data, **kwargs):
            if data["status"] == "RUNNING" and "logs" in data:
                if blocked:
                    await asyncio.Event().wait()
                raise RuntimeError("store unavailable")
            return await super().put(collection, id, data, **kwargs)

    docs = FailingProgress()
    msg = Msg()

    async def handler(ctx):
        await asyncio.sleep(0.1)
        return "done"

    _run(_host(docs, heartbeat_seconds=0.01), JobDescriptor("long"), handler, msg)
    assert msg.calls.count(("in_progress",)) >= 5
    assert docs.run("long:7")["status"] == "SUCCEEDED"
    if not blocked:
        assert "Job progress persistence failed" in caplog.text


def test_heartbeat_failure_stops_and_retries_the_handler(caplog):
    stopped = []

    class FailedRenewal(Msg):
        async def in_progress(self):
            raise RuntimeError("broker unavailable")

    async def handler(ctx):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append(True)

    docs = Documents()
    msg = FailedRenewal()
    _run(
        _host(docs, heartbeat_seconds=0.01),
        JobDescriptor("long", max_attempts=2),
        handler,
        msg,
    )
    assert stopped == [True]
    assert docs.run("long:7")["status"] == "RETRYING"
    assert msg.calls == [("nak", 5)]
    assert "Job acknowledgement heartbeat failed" in caplog.text


@pytest.mark.parametrize(
    "outcome,retire", [("success", "ack"), ("failure", "term"), ("retry", "nak")]
)
def test_completion_is_saved_before_retiring_delivery(outcome, retire):
    docs = Documents()

    class CheckedRetirement(Msg):
        async def ack(self):
            assert docs.run("ingest:7")["status"] == "SUCCEEDED"
            await super().ack()

        async def term(self):
            assert docs.run("ingest:7")["status"] == "FAILED"
            await super().term()

        async def nak(self, delay=None):
            assert docs.run("ingest:7")["status"] == "RETRYING"
            await super().nak(delay)

    async def handler(ctx):
        if outcome != "success":
            raise RuntimeError("failed")
        return 42

    msg = CheckedRetirement()
    _run(
        _host(docs),
        JobDescriptor("ingest", max_attempts=2 if outcome == "retry" else 1),
        handler,
        msg,
    )
    assert msg.calls[-1][0] == retire


def test_completion_outage_keeps_the_result_and_heartbeat_while_retrying():
    class CompletionOutage(Documents):
        failures = 3

        async def put(self, collection, id, data, **kwargs):
            if data["status"] == "SUCCEEDED" and self.failures:
                self.failures -= 1
                raise RuntimeError("store unavailable")
            return await super().put(collection, id, data, **kwargs)

    docs = CompletionOutage()
    msg = Msg()
    calls = []

    async def handler(ctx):
        calls.append(True)
        return {"answer": 42}

    _run(_host(docs, heartbeat_seconds=0.01), JobDescriptor("ingest"), handler, msg)
    assert calls == [True]
    assert msg.calls.count(("in_progress",)) >= 2
    assert msg.calls[-1] == ("ack",)
    assert docs.run("ingest:7")["result"] == {"answer": 42}


@pytest.mark.parametrize(
    "status", ["SUCCEEDED", "SKIPPED", "CANCELLED", "FAILED", "TIMED_OUT"]
)
def test_retirement_outage_redelivery_keeps_completion_without_reexecuting(status):
    docs = Documents()
    _seed(docs, "ingest", 7, status, datetime.now(timezone.utc))
    snapshot = dict(docs.run("ingest:7"))

    class FailedRetirement(Msg):
        async def ack(self):
            raise RuntimeError("broker unavailable")

        async def term(self):
            raise RuntimeError("broker unavailable")

    async def handler(ctx):
        pytest.fail("Completed delivery must not execute again")

    host = _host(docs)
    with pytest.raises(RuntimeError, match="broker unavailable"):
        _run(host, JobDescriptor("ingest"), handler, FailedRetirement())
    msg = Msg(attempt=2)
    _run(host, JobDescriptor("ingest"), handler, msg)
    assert docs.run("ingest:7") == snapshot
    assert msg.calls == [
        ("ack",) if status in ("SUCCEEDED", "SKIPPED", "CANCELLED") else ("term",)
    ]


def test_cas_exhaustion_does_not_silently_allow_execution():
    class ConflictingDocuments(Documents):
        async def put(self, *args, **kwargs):
            raise VersionConflict("VERSION_CONFLICT", "contended")

    async def handler(ctx):
        pytest.fail("A run must be saved before it starts")

    msg = Msg()
    with pytest.raises(VersionConflict):
        _run(_host(ConflictingDocuments()), JobDescriptor("ingest"), handler, msg)
    assert msg.calls == []


@pytest.mark.parametrize("failed", [False, True])
def test_retirement_failure_after_execution_preserves_the_saved_result(failed):
    docs = Documents()
    executions = []

    class FailedRetirement(Msg):
        async def ack(self):
            raise RuntimeError("ack unavailable")

        async def term(self):
            raise RuntimeError("term unavailable")

    async def handler(ctx):
        executions.append(True)
        if failed:
            raise ValueError("handler failed")
        return {"answer": 42}

    host = _host(docs)
    with pytest.raises(RuntimeError):
        _run(host, JobDescriptor("ingest"), handler, FailedRetirement())
    snapshot = dict(docs.run("ingest:7"))
    assert snapshot["status"] == ("FAILED" if failed else "SUCCEEDED")
    if not failed:
        assert snapshot["result"] == {"answer": 42}
    _run(host, JobDescriptor("ingest"), handler, Msg(attempt=2))
    assert executions == [True]
    assert docs.run("ingest:7") == snapshot


def test_shutdown_during_completion_outage_leaves_delivery_unacknowledged():
    class CompletionOutage(Documents):
        async def put(self, collection, id, data, **kwargs):
            if data["status"] == "SUCCEEDED":
                host._closing = True
                raise RuntimeError("store unavailable")
            return await super().put(collection, id, data, **kwargs)

    docs = CompletionOutage()
    host = _host(docs)
    msg = Msg()

    async def handler(ctx):
        return 42

    with pytest.raises(RuntimeError, match="store unavailable"):
        _run(host, JobDescriptor("ingest"), handler, msg)
    assert msg.calls == []
    assert not host._running and not host._work


def test_manual_idempotency_keys_do_not_suppress_other_modules_jobs():
    js = _DedupJetStream()
    hosts = [_publishing_host(js), _publishing_host(js)]
    hosts[1].module_id = "acme.other"

    async def scenario():
        for host in hosts:
            await host.trigger("ingest", idempotency_key="same")
            await host.trigger("ingest", idempotency_key="same")

    asyncio.run(scenario())
    assert len(js.published) == 2
