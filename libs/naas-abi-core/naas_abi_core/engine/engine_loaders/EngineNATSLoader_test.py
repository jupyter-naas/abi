"""Tests for EngineNATSLoader -- config-gated exposure of loaded services
over NATS. Only reads ``configuration.nats``, so a bare namespace stands in
for a full ``EngineConfiguration`` here rather than constructing one."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineNATSLoader import EngineNATSLoader
from naas_abi_core.services.object_storage.adapters.primary.object_storage__primary_adapter__NATS import (
    ObjectStoragePrimaryAdapterNATS,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNATSClient import (
    ObjectStorageSecondaryAdapterNATSClient,
)


def _services(*, object_storage_available: bool, adapter=None) -> MagicMock:
    services = MagicMock()
    services.object_storage_available.return_value = object_storage_available
    if object_storage_available:
        services.object_storage.adapter = adapter or MagicMock()
    return services


def test_expose_services_is_a_noop_without_nats_config(monkeypatch):
    loader = EngineNATSLoader(SimpleNamespace(nats=None))
    connect = MagicMock()
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.get_connection", connect)

    started = loader.expose_services(_services(object_storage_available=True))

    assert started == []
    connect.assert_not_called()


def test_expose_services_is_a_noop_when_object_storage_was_never_loaded(monkeypatch):
    config = SimpleNamespace(nats=NATSConfiguration(jwt_secret="x" * 32))
    loader = EngineNATSLoader(config)
    monkeypatch.setattr(
        "naas_abi_core.engine.nats_runtime.get_connection", MagicMock()
    )
    # Closes the coroutine it's handed instead of just swallowing it, so the
    # real ObjectStoragePrimaryAdapterNATS.start(nc) coroutine created (but
    # never awaited, since run_coro itself is mocked) doesn't trip pytest's
    # "coroutine was never awaited" warning.
    run_coro = MagicMock(side_effect=lambda coro, *a, **k: coro.close())
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.run_coro", run_coro)

    started = loader.expose_services(_services(object_storage_available=False))

    assert started == []
    run_coro.assert_not_called()


def test_expose_services_starts_a_primary_adapter_wrapping_the_domain_service(
    monkeypatch,
):
    config = SimpleNamespace(
        nats=NATSConfiguration(nats_url="nats://example:4222", jwt_secret="x" * 32)
    )
    loader = EngineNATSLoader(config)
    fake_nc = MagicMock()
    get_connection = MagicMock(return_value=fake_nc)
    run_coro = MagicMock()
    monkeypatch.setattr(
        "naas_abi_core.engine.nats_runtime.get_connection", get_connection
    )
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.run_coro", run_coro)

    services = _services(object_storage_available=True)
    started = loader.expose_services(services)

    get_connection.assert_called_once_with("nats://example:4222")
    assert len(started) == 1
    primary = started[0]
    assert isinstance(primary, ObjectStoragePrimaryAdapterNATS)
    # Wraps the domain SERVICE (services.object_storage), not
    # services.object_storage.adapter -- see the primary adapter's own
    # docstring for why (event publishing, prefix normalization).
    assert primary._adapter is services.object_storage
    run_coro.assert_called_once()


def test_expose_services_does_not_re_expose_a_remote_object_storage_client(
    monkeypatch,
):
    config = SimpleNamespace(nats=NATSConfiguration(jwt_secret="x" * 32))
    loader = EngineNATSLoader(config)
    monkeypatch.setattr(
        "naas_abi_core.engine.nats_runtime.get_connection", MagicMock()
    )
    # Closes the coroutine it's handed instead of just swallowing it, so the
    # real ObjectStoragePrimaryAdapterNATS.start(nc) coroutine created (but
    # never awaited, since run_coro itself is mocked) doesn't trip pytest's
    # "coroutine was never awaited" warning.
    run_coro = MagicMock(side_effect=lambda coro, *a, **k: coro.close())
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.run_coro", run_coro)

    remote_client = MagicMock(spec=ObjectStorageSecondaryAdapterNATSClient)
    services = _services(object_storage_available=True, adapter=remote_client)

    started = loader.expose_services(services)

    assert started == []
    run_coro.assert_not_called()
