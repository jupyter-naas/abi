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
