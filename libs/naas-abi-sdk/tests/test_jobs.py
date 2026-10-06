import asyncio
from datetime import timedelta

import pytest

from naas_abi_sdk.discovery import module_descriptor
from naas_abi_sdk.jobs import (
    Cron,
    Every,
    JobDescriptor,
    JobsMixin,
    OnEvent,
    job,
    job_subjects,
    runs_collection,
    stream_name,
)
from naas_abi_sdk.module import BaseModule, ModuleDependencies


def test_cron_is_six_fields_with_optional_time_zone():
    assert Cron("0 0 6 * * *", time_zone="Europe/Paris").headers() == {
        "Nats-Schedule": "0 0 6 * * *",
        "Nats-Schedule-Time-Zone": "Europe/Paris",
    }
    assert Cron("@daily").headers() == {"Nats-Schedule": "@daily"}
    for bad in ("0 6 * * *", "", "@fortnightly"):
        with pytest.raises(ValueError):
            Cron(bad)


def test_every_is_a_go_duration_of_at_least_a_second():
    assert Every("1h30m").headers() == {"Nats-Schedule": "@every 1h30m"}
    assert Every(timedelta(minutes=5)).headers() == {"Nats-Schedule": "@every 300s"}
    for bad in ("soon", "500ms", "", timedelta(milliseconds=10)):
        with pytest.raises(ValueError):
            Every(bad)


def test_one_go_duration_parser_serves_every_and_tick_ttls():
    from naas_abi_sdk.job_host import scheduled_tick_ttl
    from naas_abi_sdk.jobs import go_duration_seconds

    assert go_duration_seconds("1h30m") == 5400
    assert go_duration_seconds("1.5s") == 1.5
    assert go_duration_seconds("250ms") == 0.25
    for bad in ("soon", "", "10", "1h junk"):
        with pytest.raises(ValueError):
            go_duration_seconds(bad)
    assert scheduled_tick_ttl(Every("90s")) == "90s"
    assert scheduled_tick_ttl(Every("1m30s")) == "90s"
    assert scheduled_tick_ttl(Every("2s")) == "60s"  # at least a minute
    assert scheduled_tick_ttl(Every("6h")) == "3600s"  # at most an hour


def test_on_event_targets_an_event_type_or_a_raw_subject():
    import hashlib

    iri = "http://ontology.naas.ai/abi/object_storage/ObjectPut"
    digest = hashlib.sha256(iri.encode()).hexdigest()[:32]
    assert OnEvent(event_type=iri).subject == f"evt.{digest}.>"
    assert (
        OnEvent(subject="triple_store.ts.insert.>").subject
        == "triple_store.ts.insert.>"
    )
    with pytest.raises(ValueError):
        OnEvent()


def test_descriptor_round_trips_through_discovery_protobuf():
    descriptor = JobDescriptor(
        "ingest",
        "Ingest the day.",
        triggers=(
            Cron("0 0 6 * * *", time_zone="UTC"),
            Every("1h"),
            OnEvent(subject="evt.x.>"),
        ),
        max_concurrency=2,
        timeout=timedelta(minutes=30),
        max_attempts=3,
    )

    assert JobDescriptor.from_pb(descriptor.to_pb()) == descriptor
    for bad in (
        {"name": "bad name"},
        {"name": "ok", "max_concurrency": 0},
        {"name": "ok", "max_attempts": 0},
        {"name": "ok", "timeout": timedelta(0)},
    ):
        with pytest.raises(ValueError):
            JobDescriptor(**bad)


def test_subjects_hash_module_and_job_names():
    subjects = job_subjects("zen", "signals.github", "ingest")

    assert stream_name("zen") == "ABI_JOBS_zen"
    assert subjects.trigger.startswith("abi.jobs.zen.trigger.")
    assert subjects.schedule(0).startswith("abi.jobs.zen.schedule.")
    assert subjects.schedule(0).endswith(".0")
    assert subjects.cancel.startswith("abi.jobs.zen.cancel.")
    assert "signals.github" not in subjects.trigger  # dots would split tokens
    assert job_subjects("zen", "signals.github", "ingest") == subjects
    assert job_subjects("zen", "signals.github", "other").trigger != subjects.trigger
    assert runs_collection("zen").startswith("job_runs_")


class _Module(BaseModule):
    module_id = "acme.jobs"
    dependencies = ModuleDependencies(services=("document",))
    jobs = (JobDescriptor("explicit", "Bound with expose_job."),)

    @job(triggers=(Every("1m"),), max_attempts=2)
    async def nightly(self, ctx):
        """Runs every minute."""
        return "done"


def _instance(cls=_Module):
    module = object.__new__(cls)
    module._agent_handlers = {}
    return module


def test_job_decorator_declares_and_binds():
    names = {j.name: j for j in _Module.jobs}

    assert set(names) == {"explicit", "nightly"}
    assert names["nightly"].description == "Runs every minute."
    assert names["nightly"].max_attempts == 2
    module = _instance()
    assert asyncio.run(module._job_handlers["nightly"](None)) == "done"
    assert "explicit" not in module._job_handlers


def test_expose_job_validates_like_expose_agent():
    module = _instance()

    async def handler(ctx):
        return None

    module.expose_job("explicit", handler)
    with pytest.raises(ValueError, match="already"):
        module.expose_job("explicit", handler)
    with pytest.raises(ValueError, match="Declare"):
        module.expose_job("unknown", handler)
    with pytest.raises(TypeError, match="async"):
        _instance().expose_job("explicit", lambda ctx: None)


def test_sdk_modules_reject_sync_job_methods_when_defined():
    with pytest.raises(TypeError, match="must be async"):

        class _Sync(BaseModule):
            @job()
            def blocking(self, ctx):
                return None


def test_sync_jobs_mixin_accepts_sync_methods_and_handlers():
    class _Core(JobsMixin):
        _sync_jobs = True
        jobs = (JobDescriptor("explicit"),)

        @job()
        def compact(self, ctx):
            """Compacts datasets."""
            return "compacted"

    core = _Core()
    core.expose_job("explicit", lambda ctx: "sync is fine here")

    assert {j.name for j in _Core.jobs} == {"explicit", "compact"}
    assert core._job_handlers["compact"](None) == "compacted"
    assert core.missing_job_handlers() == set()
    assert _Core().missing_job_handlers() == {"explicit"}


def test_decorated_job_names_must_be_unique():
    with pytest.raises(ValueError, match="Duplicate job"):

        class _Dup(BaseModule):
            jobs = (JobDescriptor("same"),)

            @job("same")
            async def again(self, ctx):
                return None


def test_module_descriptor_lists_jobs():
    descriptor = module_descriptor(_Module, "acme.jobs", ())

    assert [j.name for j in descriptor.jobs] == ["explicit", "nightly"]
    assert descriptor.jobs[1].triggers[0].kind == "every"


def _fake_client(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", lambda *a, **k: client)


def test_run_module_requires_a_handler_for_every_declared_job(monkeypatch):
    from naas_abi_sdk.module import run_module

    _fake_client(monkeypatch)

    class Unbound(BaseModule):
        jobs = (JobDescriptor("never_bound"),)

        async def run(self):
            return None

    with pytest.raises(ValueError, match="Every declared job"):
        asyncio.run(run_module(Unbound, url="nats://unused", token="t"))


def test_run_module_requires_discovery_and_documents_to_host_jobs(monkeypatch):
    from naas_abi_sdk.module import run_module

    _fake_client(monkeypatch)

    class NoDiscovery(BaseModule):
        @job()
        async def tick(self, ctx):
            return None

        async def run(self):
            return None

    with pytest.raises(ValueError, match="Job hosting requires discovery"):
        asyncio.run(run_module(NoDiscovery, url="nats://unused", token="t"))


def _staging(monkeypatch, events):
    """Discovery that stages a rollout's generation, and a recording job host."""

    class Session:
        def __init__(self, client, descriptor, rollout_id="", rollout_modules=()):
            self.rollout_id, self.instance_id = rollout_id, "instance"
            self.initialized = self.draining = False
            self.status, self.task = "STARTING", None
            self.drain_requested = asyncio.Event()

        async def start(self):
            events.append("register")

        async def renew(self):
            events.append("renew")
            if self.initialized and self.status == "STARTING":
                self.status = "STAGED" if self.rollout_id else "READY"

        async def close(self):
            pass

    class Host:
        def __init__(self, *args, **kwargs):
            pass

        async def start(self):
            events.append("jobs")

        async def drain(self, timeout):
            pass

        async def close(self):
            events.append("jobs closed")

    monkeypatch.setattr("naas_abi_sdk.module.DiscoverySession", Session)
    monkeypatch.setattr("naas_abi_sdk.job_host.JobHost", Host)


class _Ticking(BaseModule):
    module_id = "acme.ticking"
    dependencies = ModuleDependencies(services=("document",))

    @job()
    async def tick(self, ctx):
        return None


def test_a_staged_generation_hosts_its_jobs_only_after_the_cutover(monkeypatch):
    from naas_abi_sdk.discovery import DiscoveryConfiguration
    from naas_abi_sdk.module import run_module

    events: list[str] = []
    _fake_client(monkeypatch)
    _staging(monkeypatch, events)

    class Staged(_Ticking):
        async def run(self):
            session = self._discovery_session
            assert session.status == "STAGED"
            await asyncio.sleep(0.05)
            # Schedules and consumers are module-wide: the live generation keeps them.
            assert "jobs" not in events
            session.status = "READY"  # its cohort is up; a renewal says so
            for _ in range(200):
                if "jobs" in events:
                    break
                await asyncio.sleep(0.01)
            return list(events)

    seen = asyncio.run(
        run_module(
            Staged,
            url="nats://unused",
            token="t",
            discovery=DiscoveryConfiguration(
                rollout_id="release-2", refresh_seconds=0.01
            ),
        )
    )
    assert seen == ["register", "renew", "jobs"]
    assert events[-1] == "jobs closed"


def test_jobs_start_before_readiness_outside_a_rollout(monkeypatch):
    from naas_abi_sdk.discovery import DiscoveryConfiguration
    from naas_abi_sdk.module import run_module

    events: list[str] = []
    _fake_client(monkeypatch)
    _staging(monkeypatch, events)

    class Plain(_Ticking):
        async def run(self):
            return list(events)

    seen = asyncio.run(
        run_module(
            Plain, url="nats://unused", token="t", discovery=DiscoveryConfiguration()
        )
    )
    assert seen == ["register", "jobs", "renew"]


def test_a_staged_generation_that_drains_never_hosts_its_jobs(monkeypatch):
    from naas_abi_sdk.discovery import DiscoveryConfiguration
    from naas_abi_sdk.module import run_module

    events: list[str] = []
    _fake_client(monkeypatch)
    _staging(monkeypatch, events)

    class Abandoned(_Ticking):
        async def run(self):
            await asyncio.sleep(0.05)
            self._discovery_session.drain_requested.set()  # SIGTERM while staged
            await asyncio.Event().wait()

    assert (
        asyncio.run(
            run_module(
                Abandoned,
                url="nats://unused",
                token="t",
                discovery=DiscoveryConfiguration(
                    rollout_id="release-2", refresh_seconds=0.01
                ),
            )
        )
        is None
    )
    assert "jobs" not in events


def test_failing_to_host_jobs_after_the_cutover_stops_the_module(monkeypatch):
    from naas_abi_sdk import job_host
    from naas_abi_sdk.discovery import DiscoveryConfiguration
    from naas_abi_sdk.module import run_module

    events: list[str] = []
    _fake_client(monkeypatch)
    _staging(monkeypatch, events)

    class Refused(job_host.JobHost):
        async def start(self):
            raise RuntimeError("consumer refused")

    monkeypatch.setattr("naas_abi_sdk.job_host.JobHost", Refused)

    class Staged(_Ticking):
        async def run(self):
            self._discovery_session.status = "READY"
            await asyncio.Event().wait()

    with pytest.raises(RuntimeError, match="consumer refused"):
        asyncio.run(
            run_module(
                Staged,
                url="nats://unused",
                token="t",
                discovery=DiscoveryConfiguration(
                    rollout_id="release-2", refresh_seconds=0.01
                ),
            )
        )
    assert events[-1] == "jobs closed"


def test_client_reaches_any_modules_job_by_name_without_discovery():
    from naas_abi_sdk.client import ABIClient
    from naas_abi_sdk.jobs import JobProxy

    client = ABIClient("nats://127.0.0.1:4222", "token")
    proxy = client.get_job("signals.github", "ingest", project="zen")

    assert isinstance(proxy, JobProxy)
    assert (proxy.project, proxy.module_id, proxy.name) == (
        "zen",
        "signals.github",
        "ingest",
    )
    assert proxy.transport is client._transport


# --- event filters, skipped runs, a module triggering its own jobs -----------------------


def test_on_event_filters_match_event_fields_and_round_trip():
    from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

    puts = OnEvent(
        event_type="http://ontology.naas.ai/abi/ObjectPut",
        filter={"prefix": {"prefix": "naas/"}, "size_bytes": {"gt": 0}},
    )

    assert puts.matches({"prefix": "naas/mercury", "size_bytes": 3})
    assert not puts.matches({"prefix": "other/", "size_bytes": 3})
    assert not puts.matches("not an object")
    assert OnEvent("evt.x.>").matches({"anything": 1})  # no filter: every event
    descriptor = JobDescriptor("ingest", triggers=(puts,))
    back = JobDescriptor.from_pb(
        pb.JobDescriptor.FromString(descriptor.to_pb().SerializeToString())
    )
    assert back == descriptor and back.triggers[0].filter == puts.filter


@pytest.mark.parametrize(
    "bad", [{"a": {"bogus": 1}}, {"a b": 1}, {"": 1}, ["not", "a", "dict"]]
)
def test_malformed_event_filters_are_refused_when_declared(bad):
    with pytest.raises((ValueError, TypeError)):
        OnEvent("evt.x.>", filter=bad)


def test_a_handler_can_say_a_run_did_nothing():
    from naas_abi_sdk.jobs import TERMINAL_STATUSES, JobContext

    ctx = JobContext("ingest:1", "ingest", 1, {}, {})
    assert ctx.skipped is None
    ctx.skip("no new dumps")

    assert ctx.skipped == "no new dumps"
    assert "SKIPPED" in TERMINAL_STATUSES


class _SelfTriggering(JobsMixin):
    jobs = (JobDescriptor("ingest"),)


class _Host:
    def __init__(self):
        self.calls = []

    async def trigger(self, name, payload=None, *, idempotency_key=None):
        import threading

        self.calls.append(
            (name, payload, idempotency_key, threading.current_thread().name)
        )
        return f"run-of-{name}"


def _loop_thread():
    import threading

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, name="host-loop", daemon=True)
    thread.start()
    return loop, thread


def test_a_module_triggers_its_own_jobs_once_they_are_hosted():
    from naas_abi_sdk.jobs import JobsNotHosted

    module = _SelfTriggering()
    with pytest.raises(JobsNotHosted):
        module.trigger_job("ingest")
    with pytest.raises(JobsNotHosted):
        asyncio.run(module.atrigger_job("ingest"))

    host, (loop, thread) = _Host(), _loop_thread()
    try:
        module._bind_job_host(host, loop)
        # From sync code (an engine request thread) and from another loop alike,
        # the trigger runs on the host's loop.
        assert module.trigger_job("ingest", {"x": 1}, idempotency_key="k") == (
            "run-of-ingest"
        )
        assert asyncio.run(module.atrigger_job("ingest")) == "run-of-ingest"
        assert host.calls == [
            ("ingest", {"x": 1}, "k", "host-loop"),
            ("ingest", None, None, "host-loop"),
        ]
        # On the host's own loop the blocking form would deadlock: refuse it.
        blocked = asyncio.run_coroutine_threadsafe(
            _call_sync_on_loop(module), loop
        ).result(5)
        assert isinstance(blocked, RuntimeError)
        module._bind_job_host(None, None)
        with pytest.raises(JobsNotHosted):
            module.trigger_job("ingest")
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)


async def _call_sync_on_loop(module):
    try:
        module.trigger_job("ingest")
    except RuntimeError as exc:
        return exc
    return None
