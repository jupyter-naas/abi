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
