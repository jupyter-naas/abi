"""Kernel jobs offered by service adapters (Engine.job_owners)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from naas_abi_core.engine.Engine import Engine
from naas_abi_core.services.dataset.DatasetMaintenanceJobs import (
    DATASET_JOBS_OWNER,
    DatasetMaintenanceJobs,
)


class ArchivingAdapter:
    def job_owners(self, services):
        self.received = services
        return {"naas_abi_core.event_archive": "archive owner"}


def bare_engine(nats, *services, dataset=None, facades=None) -> Engine:
    """``dataset`` is the engine's own dataset service; ``facades`` the NATS
    view handed to modules and dependencies (``Engine.services``)."""
    engine = Engine.__new__(Engine)
    engine._Engine__modules = {"some.module": "module"}  # type: ignore[attr-defined]
    engine._Engine__configuration = SimpleNamespace(nats=nats)  # type: ignore[attr-defined]
    engine._Engine__nats_dependencies = (  # type: ignore[attr-defined]
        None if facades is None else SimpleNamespace(module_services=facades)
    )
    engine._Engine__services = SimpleNamespace(  # type: ignore[attr-defined]
        all=list(services),
        dataset_available=lambda: dataset is not None,
        dataset=dataset,
    )
    return engine


def test_service_adapters_offer_kernel_jobs_in_nats_mode():
    adapter = ArchivingAdapter()
    engine = bare_engine(object(), SimpleNamespace(adapter=adapter), None)

    assert engine.job_owners() == {
        "some.module": "module",
        "naas_abi_core.event_archive": "archive owner",
    }
    assert adapter.received is engine.services


def test_adapters_without_jobs_offer_none():
    engine = bare_engine(object(), SimpleNamespace(adapter=MagicMock()), object())

    assert engine.job_owners() == {"some.module": "module"}


def test_without_nats_no_kernel_jobs_are_hosted():
    engine = bare_engine(None, SimpleNamespace(adapter=ArchivingAdapter()))

    assert engine.job_owners() == {"some.module": "module"}


def test_dataset_maintenance_runs_on_the_engines_own_dataset_service():
    """Compaction maintains the owner's data: no NATS hop, no RPC deadline."""
    owner, facade = object(), object()
    engine = bare_engine(
        object(), dataset=owner, facades=SimpleNamespace(dataset=facade)
    )

    jobs = engine.job_owners()[DATASET_JOBS_OWNER]

    assert isinstance(jobs, DatasetMaintenanceJobs)
    assert jobs.service is owner


def test_cross_domain_jobs_offered_by_adapters_keep_the_network_facades():
    """The event archive writes to another domain (datasets): it goes over NATS."""
    adapter = ArchivingAdapter()
    facades = SimpleNamespace(dataset=object())
    engine = bare_engine(
        object(), SimpleNamespace(adapter=adapter), dataset=object(), facades=facades
    )

    engine.job_owners()

    assert adapter.received is facades
