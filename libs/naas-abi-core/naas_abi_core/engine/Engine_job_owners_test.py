"""Kernel jobs offered by service adapters (Engine.job_owners)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from naas_abi_core.engine.Engine import Engine


class ArchivingAdapter:
    def job_owners(self, services):
        self.received = services
        return {"naas_abi_core.event_archive": "archive owner"}


def bare_engine(nats, *services) -> Engine:
    engine = Engine.__new__(Engine)
    engine._Engine__modules = {"some.module": "module"}  # type: ignore[attr-defined]
    engine._Engine__configuration = SimpleNamespace(nats=nats)  # type: ignore[attr-defined]
    engine._Engine__nats_dependencies = None  # type: ignore[attr-defined]
    engine._Engine__services = SimpleNamespace(  # type: ignore[attr-defined]
        all=list(services), dataset_available=lambda: False
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
