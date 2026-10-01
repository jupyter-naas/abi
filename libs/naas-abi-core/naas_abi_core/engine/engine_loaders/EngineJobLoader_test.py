import asyncio
import threading

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    DiscoveryConfiguration,
    NATSConfiguration,
    NATSJobsConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineJobLoader import (
    EngineJobLoader,
    as_async_handler,
)
from naas_abi_core.module.jobs import JobDescriptor, JobsMixin, job

SECRET = "engine-job-loader-test-secret-32-bytes"


class _Jobs(JobsMixin):
    _sync_jobs = True

    @job()
    def compact(self, ctx):
        """Compacts datasets."""
        return threading.current_thread().name


class _NoJobs(JobsMixin):
    _sync_jobs = True


class _Unbound(JobsMixin):
    _sync_jobs = True
    jobs = (JobDescriptor("declared_only"),)


class _Host:
    def __init__(self, transport, documents, module_id, project, handlers, **kwargs):
        self.module_id, self.project, self.handlers = module_id, project, handlers
        self.documents, self.kwargs = documents, kwargs
        self.started = self.closed = False

    async def start(self):
        self.started = True

    async def close(self):
        self.closed = True


def _config(**jobs):
    return NATSConfiguration(
        jwt_secret=SECRET,
        discovery=DiscoveryConfiguration(project="zen"),
        jobs=NATSJobsConfiguration(**jobs),
    )


def _loader(config, hosts):
    def host_factory(*args, **kwargs):
        hosts.append(_Host(*args, **kwargs))
        return hosts[-1]

    return EngineJobLoader(
        config,
        documents_factory=lambda transport, module_id: f"docs:{module_id}",
        host_factory=host_factory,
    )


def test_one_host_per_module_with_jobs_in_the_discovery_project():
    hosts: list[_Host] = []
    loader = _loader(_config(), hosts)

    loader.start(
        {"acme.jobs": _Jobs(), "acme.quiet": _NoJobs()}, document_available=True
    )
    try:
        assert [h.module_id for h in hosts] == ["acme.jobs"]
        (host,) = hosts
        assert host.started and host.project == "zen"
        assert host.documents == "docs:acme.jobs"
        assert set(host.handlers) == {"compact"}
        assert host.kwargs["instance_id"].startswith("engine-")
    finally:
        loader.stop()

    assert host.closed
    assert loader.hosts == []


def test_sync_handlers_run_in_their_own_interruptible_thread():
    from naas_abi_core.engine.engine_loaders.SyncJobRunner import SyncJobRunner
    from naas_abi_core.module.jobs import JobContext

    handler = as_async_handler(
        _Jobs()._job_handlers["compact"], interrupt_grace_seconds=2
    )

    async def run():
        ctx = JobContext("compact:1", "compact", 1, {"kind": "manual"}, {})
        return await handler(ctx), threading.current_thread().name

    worker, loop_thread = asyncio.run(run())
    assert isinstance(handler, SyncJobRunner)
    assert handler.interrupt_grace_seconds == 2
    assert worker == "abi-job-compact:1" != loop_thread


def test_async_handlers_are_used_as_is():
    async def handler(ctx):
        return None

    assert as_async_handler(handler) is handler


def test_declared_jobs_need_handlers():
    loader = _loader(_config(), [])

    with pytest.raises(ValueError, match="declared_only"):
        loader.start({"acme.unbound": _Unbound()}, document_available=True)
    loader.stop()


def test_jobs_need_the_document_service_for_run_records():
    loader = _loader(_config(), [])

    with pytest.raises(ValueError, match="document service"):
        loader.start({"acme.jobs": _Jobs()}, document_available=False)
    loader.stop()


def test_disabled_or_non_nats_engines_host_nothing():
    for config in (_config(enabled=False), None):
        hosts: list[_Host] = []
        loader = _loader(config, hosts)
        loader.start({"acme.jobs": _Jobs()}, document_available=True)
        loader.stop()
        assert hosts == []


def test_project_defaults_without_discovery():
    hosts: list[_Host] = []
    loader = _loader(NATSConfiguration(jwt_secret=SECRET), hosts)

    loader.start({"acme.jobs": _Jobs()}, document_available=True)
    loader.stop()

    assert hosts[0].project == "default"


def test_engine_adds_dataset_maintenance_as_a_kernel_job_owner_in_nats_mode():
    from types import SimpleNamespace

    from naas_abi_core.engine.Engine import Engine
    from naas_abi_core.services.dataset.DatasetMaintenanceJobs import (
        DATASET_JOBS_OWNER,
        DatasetMaintenanceJobs,
    )

    def engine(nats):
        e = Engine.__new__(Engine)
        e._Engine__configuration = SimpleNamespace(nats=nats)  # type: ignore[attr-defined]
        e._Engine__nats_dependencies = None  # type: ignore[attr-defined]
        e._Engine__modules = {"acme.jobs": _Jobs()}  # type: ignore[attr-defined]
        e._Engine__services = SimpleNamespace(  # type: ignore[attr-defined]
            dataset_available=lambda: True, dataset=object()
        )
        return e

    nats = engine(_config())
    owners = nats.job_owners()
    assert set(owners) == {"acme.jobs", DATASET_JOBS_OWNER}
    assert isinstance(owners[DATASET_JOBS_OWNER], DatasetMaintenanceJobs)
    assert nats.hosts_jobs
    legacy = engine(None)
    assert set(legacy.job_owners()) == {"acme.jobs"}
    assert not legacy.hosts_jobs
    assert not engine(_config(enabled=False)).hosts_jobs
