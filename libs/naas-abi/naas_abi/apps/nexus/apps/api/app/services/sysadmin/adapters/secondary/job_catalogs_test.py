import asyncio
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
            triggers.append(Cron(t.spec, time_zone=t.time_zone))
        elif t.kind == "every":
            triggers.append(Every(t.spec))
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


def test_the_jobs_of_a_remote_workflow_and_pipeline_are_listed_under_their_module():
    """What discovery hands back for a module whose processes declare ``job``."""
    pytest.importorskip("pydantic")
    pytest.importorskip("rdflib")
    from naas_abi_proto.discovery.v1 import discovery_pb2
    from naas_abi_sdk.discovery import _instance, module_descriptor
    from naas_abi_sdk.jobs import JobSettings
    from naas_abi_sdk.module import BaseModule
    from naas_abi_sdk.pipeline import Pipeline
    from naas_abi_sdk.workflow import Workflow

    class IngestPipeline(Pipeline):
        """Loads the nightly export."""

        job = JobSettings(triggers=(Every("1h"),), timeout=timedelta(minutes=10))

    class ExportWorkflow(Workflow):
        job = JobSettings(max_attempts=3)

    class QuietWorkflow(Workflow):
        """Declares no job."""

    class ABIModule(BaseModule):
        module_id = "acme.process"
        workflows = (ExportWorkflow, QuietWorkflow)
        pipelines = (IngestPipeline,)

    instance = _instance(
        discovery_pb2.Instance(
            instance_id="p-1",
            status="READY",
            descriptor=module_descriptor(ABIModule, "acme.process", ()),
        )
    )

    class Discovery:
        async def list_modules(self, *, limit, after_instance_id):
            return [instance], ""

    jobs = {j.key: j for j in asyncio.run(DiscoveryJobCatalog(Discovery).list_jobs())}

    assert sorted(jobs) == [
        "acme.process/pipeline.ingest_pipeline",
        "acme.process/workflow.export_workflow",
    ]
    ingest = jobs["acme.process/pipeline.ingest_pipeline"]
    assert ingest.location == "remote" and ingest.module_id == "acme.process"
    assert ingest.description == "Loads the nightly export."
    assert [(t.kind, t.spec) for t in ingest.triggers] == [("every", "1h")]
    assert ingest.timeout_seconds == 600
    export = jobs["acme.process/workflow.export_workflow"]
    assert export.triggers == () and export.max_attempts == 3
