import asyncio
import json
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.job_catalogs import (
    DiscoveryJobCatalog,
    EngineJobCatalog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import JobCatalogContract
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_sdk.jobs import Cron, Every, JobDescriptor, OnEvent


def _sdk(definition):
    """The SDK descriptor a module declares for a fixture definition."""
    triggers = []
    for t in definition.triggers:
        if t.kind == "cron":
            triggers.append(Cron(t.spec, time_zone=t.time_zone, input=t.input))
        elif t.kind == "every":
            triggers.append(Every(t.spec, input=t.input))
        else:
            triggers.append(OnEvent(t.spec))
    return JobDescriptor(
        definition.name,
        description=definition.description,
        triggers=tuple(triggers),
        max_concurrency=definition.max_concurrency,
        max_attempts=definition.max_attempts,
        timeout=timedelta(seconds=definition.timeout_seconds)
        if definition.timeout_seconds
        else None,
        kind=definition.kind,
        input_schema=json.dumps(definition.input_schema) if definition.input_schema else "",
        output_schema=json.dumps(definition.output_schema) if definition.output_schema else "",
    )


def _engine_expected():
    return [d for d in fixtures.job_definitions() if d.location == "engine"]


def _remote_expected():
    return [d for d in fixtures.job_definitions() if d.location == "remote"]


class TestEngineJobCatalog(JobCatalogContract):
    @pytest.fixture
    def expected(self):
        return _engine_expected()

    @pytest.fixture
    def catalog(self, expected):
        module = SimpleNamespace(jobs=tuple(_sdk(d) for d in expected))
        return EngineJobCatalog(lambda: {"acme.jobs": module, "acme.quiet": SimpleNamespace()})


class _Discovery:
    """Two live instances of acme.other, both declaring ``report``."""

    def __init__(self, descriptors):
        self.descriptors = descriptors

    async def list_modules(self, *, limit, after_instance_id):
        instance = lambda iid: SimpleNamespace(  # noqa: E731
            module_id="acme.other", instance_id=iid, jobs=self.descriptors
        )
        if not after_instance_id:
            return [instance("r-1")], "r-1"
        return [instance("r-2")], ""


class TestDiscoveryJobCatalog(JobCatalogContract):
    @pytest.fixture
    def expected(self):
        return _remote_expected()

    @pytest.fixture
    def catalog(self, expected):
        return DiscoveryJobCatalog(lambda: _Discovery(tuple(_sdk(d) for d in expected)))


class _OneInstance:
    def __init__(self, module_id, descriptors):
        self.module_id, self.descriptors = module_id, descriptors

    async def list_modules(self, *, limit, after_instance_id):
        return [
            SimpleNamespace(module_id=self.module_id, instance_id="f-1", jobs=self.descriptors)
        ], ""


class TestEngineJobCatalogWorkflows(JobCatalogContract):
    """Workflows come with their kind, schemas and trigger inputs."""

    @pytest.fixture
    def expected(self):
        return [replace(d, location="engine") for d in fixtures.workflow_definitions()]

    @pytest.fixture
    def catalog(self, expected):
        module = SimpleNamespace(jobs=tuple(_sdk(d) for d in expected))
        return EngineJobCatalog(lambda: {"acme.flows": module})


class TestDiscoveryJobCatalogWorkflows(JobCatalogContract):
    @pytest.fixture
    def expected(self):
        return fixtures.workflow_definitions()

    @pytest.fixture
    def catalog(self, expected):
        descriptors = tuple(_sdk(d) for d in expected)
        return DiscoveryJobCatalog(lambda: _OneInstance("acme.flows", descriptors))


def test_a_descriptor_without_kind_or_schemas_is_a_plain_job():
    # A descriptor from before workflows existed, or a core stand-in.
    old = SimpleNamespace(name="ping", description="", triggers=(), timeout=None)

    (job,) = asyncio.run(
        EngineJobCatalog(lambda: {"a.b": SimpleNamespace(jobs=(old,))}).list_jobs()
    )

    assert (job.kind, job.input_schema, job.output_schema) == ("job", None, None)


def test_schemas_and_trigger_inputs_given_as_text_or_objects_are_read():
    descriptor = SimpleNamespace(
        name="flow",
        kind="workflow",
        input_schema='{"type": "object"}',
        output_schema={"type": "string"},
        triggers=(SimpleNamespace(kind="every", interval="1h", input='{"n": 1}'),),
    )

    (job,) = asyncio.run(
        EngineJobCatalog(lambda: {"a.b": SimpleNamespace(jobs=(descriptor,))}).list_jobs()
    )

    assert job.input_schema == {"type": "object"} and job.output_schema == {"type": "string"}
    assert job.triggers[0].input == {"n": 1}


@pytest.mark.parametrize("text", ["", "not json", "[1, 2]", "{}", "3"])
def test_a_schema_that_is_empty_or_not_an_object_is_none(text):
    descriptor = SimpleNamespace(name="flow", kind="workflow", input_schema=text, triggers=())

    (job,) = asyncio.run(
        EngineJobCatalog(lambda: {"a.b": SimpleNamespace(jobs=(descriptor,))}).list_jobs()
    )

    assert job.input_schema is None


def test_during_a_rollout_the_serving_generation_defines_the_jobs():
    old = (JobDescriptor("report", triggers=(Every("1h"),)), JobDescriptor("retired"))
    new = (JobDescriptor("report", triggers=(Every("2h"),)), JobDescriptor("added"))

    class Rollout:
        async def list_modules(self, *, limit, after_instance_id):
            def instance(iid, status, jobs):
                return SimpleNamespace(
                    module_id="acme.other", instance_id=iid, status=status, jobs=jobs
                )

            return [
                instance("a-draining", "DRAINING", old),
                instance("b-staged", "STAGED", new),
                instance("c-ready", "READY", new),
            ], ""

    # Staged: listed nowhere (it hosts no jobs before the cutover).
    jobs = {j.name: j for j in asyncio.run(DiscoveryJobCatalog(Rollout).list_jobs())}

    assert sorted(jobs) == ["added", "report", "retired"]
    assert jobs["report"].triggers[0].spec == "2h"
    assert (jobs["report"].instances, jobs["added"].instances) == (2, 1)
    assert jobs["retired"].instances == 1  # until the old generation exits


def test_discovery_errors_are_an_unavailable_source():
    class Broken:
        async def list_modules(self, **_):
            raise TimeoutError("no responders")

    with pytest.raises(SourceUnavailable) as exc:
        asyncio.run(DiscoveryJobCatalog(Broken).list_jobs())
    assert exc.value.source == "discovery" and "no responders" in exc.value.reason


def test_a_broken_engine_module_does_not_hide_the_others():
    class Broken:
        @property
        def jobs(self):
            raise RuntimeError("boom")

    ok = SimpleNamespace(jobs=(JobDescriptor("ping"),))
    jobs = asyncio.run(EngineJobCatalog(lambda: {"a.broken": Broken(), "b.ok": ok}).list_jobs())

    assert [j.key for j in jobs] == ["b.ok/ping"]
