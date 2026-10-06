"""Engine.load and shutdown with the ownership lease (NATS mode)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from naas_abi_core.engine.ownership.ownership_service import (
    Claim,
    EngineAlreadyServing,
)
from naas_abi_core.engine.ownership.tests.lease__secondary_adapter__generic_test import (
    holder,
)

CONFIG = (
    "api: {}\n"
    "global_config: {ai_mode: cloud, skip_ontology_loading: true}\n"
    "modules: []\n"
    "services: {secret: {secret_adapters: []}}\n"
    "nats: {jwt_secret: test-secret}\n"
)


def primary(order: list[str]) -> MagicMock:
    adapter = MagicMock()
    adapter.stop = AsyncMock(side_effect=lambda: order.append("stop_primary"))
    return adapter


@pytest.fixture
def parts(monkeypatch):
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_core.engine.engine_loaders.EngineJobLoader import EngineJobLoader
    from naas_abi_core.engine.engine_loaders.EngineNATSLoader import EngineNATSLoader
    from naas_abi_core.engine.engine_loaders.EngineOwnershipLoader import (
        EngineOwnershipLoader,
    )

    order: list[str] = []
    found = SimpleNamespace(
        order=order,
        claim=MagicMock(return_value=Claim.SERVING),
        keep=MagicMock(),
        take_over=MagicMock(),
        release=MagicMock(side_effect=lambda: order.append("release")),
        close=MagicMock(side_effect=lambda: order.append("close_lease")),
        start_jobs=MagicMock(side_effect=lambda *a, **k: order.append("start_jobs")),
        stop_jobs=MagicMock(side_effect=lambda: order.append("stop_jobs")),
        expose=MagicMock(side_effect=lambda services: [primary(order)]),
    )
    # The endpoints are stubbed: built-in modules must not query them.
    monkeypatch.setattr(Engine, "on_initialized", lambda self: None)
    monkeypatch.setattr(EngineOwnershipLoader, "claim", found.claim)
    monkeypatch.setattr(EngineOwnershipLoader, "keep", found.keep)
    monkeypatch.setattr(
        EngineOwnershipLoader, "take_over_in_background", found.take_over
    )
    monkeypatch.setattr(EngineOwnershipLoader, "release", found.release)
    monkeypatch.setattr(EngineOwnershipLoader, "close", found.close)
    monkeypatch.setattr(EngineJobLoader, "start", found.start_jobs)
    monkeypatch.setattr(EngineJobLoader, "stop", found.stop_jobs)
    monkeypatch.setattr(EngineNATSLoader, "expose_services", found.expose)
    monkeypatch.setattr(EngineNATSLoader, "expose_overflow", lambda self, primaries: [])
    monkeypatch.setattr(
        "naas_abi_core.engine.nats_runtime.run_coro",
        lambda coro, *a, **k: __import__("asyncio").run(coro),
    )
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.close", MagicMock())
    return found


def new_engine():
    from naas_abi_core.engine.Engine import Engine

    return Engine(CONFIG)


def test_a_serving_engine_exposes_hosts_jobs_and_keeps_its_lease(parts):
    engine = new_engine()

    engine.load()

    parts.expose.assert_called_once()
    parts.start_jobs.assert_called_once()
    parts.keep.assert_called_once()
    parts.take_over.assert_not_called()
    engine.shutdown()


def test_a_client_engine_serves_nothing_and_hosts_no_jobs(parts):
    parts.claim.return_value = None
    engine = new_engine()

    engine.load()

    parts.expose.assert_not_called()
    parts.start_jobs.assert_not_called()
    parts.keep.assert_not_called()
    parts.take_over.assert_not_called()
    engine.shutdown()


def test_a_standby_engine_serves_and_hosts_jobs_only_after_the_handover(parts):
    parts.claim.return_value = Claim.STANDBY
    engine = new_engine()

    engine.load()

    parts.expose.assert_not_called()
    parts.start_jobs.assert_not_called()
    start_serving = parts.take_over.call_args.args[0]
    start_serving()
    parts.expose.assert_called_once()
    parts.start_jobs.assert_called_once()
    engine.shutdown()


def test_an_engine_that_finds_another_serving_fails_before_loading_services(
    parts, monkeypatch
):
    from naas_abi_core.engine.engine_loaders.EngineServiceLoader import (
        EngineServiceLoader,
    )

    load_services = MagicMock()
    monkeypatch.setattr(EngineServiceLoader, "load_services", load_services)
    parts.claim.side_effect = EngineAlreadyServing(holder("other"))
    engine = new_engine()

    with pytest.raises(EngineAlreadyServing):
        engine.load()

    load_services.assert_not_called()
    parts.expose.assert_not_called()
    engine.shutdown()
    parts.close.assert_called_once()


def test_fencing_stops_serving_and_restoring_serves_again(parts):
    engine = new_engine()
    engine.load()
    callbacks = parts.keep.call_args.kwargs

    callbacks["on_fenced"]()
    assert parts.order[-1] == "stop_primary"

    callbacks["on_restored"]()
    assert parts.expose.call_count == 2
    engine.shutdown()


def test_shutdown_releases_the_lease_after_jobs_and_before_the_primaries(parts):
    engine = new_engine()
    engine.load()
    parts.order.clear()

    engine.shutdown()
    engine.shutdown()

    assert parts.order == ["stop_jobs", "release", "stop_primary", "close_lease"]


def test_a_rollout_on_local_backends_fails_before_any_backend_opens(monkeypatch):
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_core.engine.engine_loaders.EngineOwnershipLoader import (
        EngineOwnershipLoader,
    )
    from naas_abi_core.engine.engine_loaders.EngineServiceLoader import (
        EngineServiceLoader,
    )
    from naas_abi_core.engine.ownership.ownership_service import (
        LocalBackendsCannotHandOver,
    )

    monkeypatch.setenv("ABI_ROLLOUT_ID", "v2")
    load_services = MagicMock()
    monkeypatch.setattr(EngineServiceLoader, "load_services", load_services)
    lease = MagicMock(side_effect=AssertionError("the lease must not be touched"))
    monkeypatch.setattr(EngineOwnershipLoader, "_jetstream_ownership", lease)
    engine = Engine(CONFIG)  # every service on its default, local adapter

    with pytest.raises(LocalBackendsCannotHandOver) as raised:
        engine.load()

    assert "document" in raised.value.local_backends
    load_services.assert_not_called()
    lease.assert_not_called()
    engine.shutdown()
