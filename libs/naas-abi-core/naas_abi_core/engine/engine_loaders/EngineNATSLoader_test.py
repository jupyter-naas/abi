"""Tests for EngineNATSLoader -- config-gated exposure of loaded services
over NATS. Only reads ``configuration.nats``, so a bare namespace stands in
for a full ``EngineConfiguration`` here rather than constructing one.

Covers every service ``expose_services`` knows how to wire, generically
(see ``_WIRED_SERVICES`` below), plus a couple of object_storage-specific
assertions kept from the original single-service version of this loader
(it's still a fine representative case: wraps the domain service, not the
raw adapter).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineNATSLoader import EngineNATSLoader
from naas_abi_core.services.activity_log.adapters.primary.activity_log__primary_adapter__NATS import (
    ActivityLogPrimaryAdapterNATS,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSecondaryAdapterNATSClient import (
    ActivityLogSecondaryAdapterNATSClient,
)
from naas_abi_core.services.coding_environment.adapters.primary.coding_environment__primary_adapter__NATS import (
    CodingEnvironmentPrimaryAdapterNATS,
)
from naas_abi_core.services.coding_environment.adapters.secondary.CodingEnvironmentSecondaryAdapterNATSClient import (
    CodingEnvironmentSecondaryAdapterNATSClient,
)
from naas_abi_core.services.dataset.adapters.primary.dataset__primary_adapter__NATS import (
    DatasetPrimaryAdapterNATS,
)
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterNATSClient import (
    DatasetSecondaryAdapterNATSClient,
)
from naas_abi_core.services.email.adapters.primary.email__primary_adapter__NATS import (
    EmailPrimaryAdapterNATS,
)
from naas_abi_core.services.email.adapters.secondary.EmailSecondaryAdapterNATSClient import (
    EmailSecondaryAdapterNATSClient,
)
from naas_abi_core.services.event.adapters.primary.event__primary_adapter__NATS import (
    EventPrimaryAdapterNATS,
)
from naas_abi_core.services.event.adapters.secondary.EventSecondaryAdapterNATSClient import (
    EventSecondaryAdapterNATSClient,
)
from naas_abi_core.services.keyvalue.adapters.primary.keyvalue__primary_adapter__NATS import (
    KeyValuePrimaryAdapterNATS,
)
from naas_abi_core.services.keyvalue.adapters.secondary.KeyValueSecondaryAdapterNATSClient import (
    KeyValueSecondaryAdapterNATSClient,
)
from naas_abi_core.services.object_storage.adapters.primary.object_storage__primary_adapter__NATS import (
    ObjectStoragePrimaryAdapterNATS,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNATSClient import (
    ObjectStorageSecondaryAdapterNATSClient,
)
from naas_abi_core.services.source_control.adapters.primary.source_control__primary_adapter__NATS import (
    SourceControlPrimaryAdapterNATS,
)
from naas_abi_core.services.source_control.adapters.secondary.SourceControlSecondaryAdapterNATSClient import (
    SourceControlSecondaryAdapterNATSClient,
)
from naas_abi_core.services.triple_store.adapters.primary.triple_store__primary_adapter__NATS import (
    TripleStorePrimaryAdapterNATS,
)
from naas_abi_core.services.triple_store.adapters.secondary.TripleStoreSecondaryAdapterNATSClient import (
    TripleStoreSecondaryAdapterNATSClient,
)
from naas_abi_core.services.vector_store.adapters.primary.vector_store__primary_adapter__NATS import (
    VectorStorePrimaryAdapterNATS,
)
from naas_abi_core.services.vector_store.adapters.secondary.VectorStoreSecondaryAdapterNATSClient import (
    VectorStoreSecondaryAdapterNATSClient,
)

# (available_flag, primary_class, client_class, wraps_raw_adapter)
# wraps_raw_adapter=True means the primary is constructed from
# services.<x>.adapter (event, vector_store -- no richer domain-level
# behaviour to preserve at that port boundary); False means it's
# constructed from services.<x> itself, the domain service (everyone else
# -- preserves event publishing / derived behaviour for remote callers).
_WIRED_SERVICES = [
    ("object_storage", ObjectStoragePrimaryAdapterNATS, ObjectStorageSecondaryAdapterNATSClient, False),
    ("dataset", DatasetPrimaryAdapterNATS, DatasetSecondaryAdapterNATSClient, False),
    ("kv", KeyValuePrimaryAdapterNATS, KeyValueSecondaryAdapterNATSClient, False),
    ("email", EmailPrimaryAdapterNATS, EmailSecondaryAdapterNATSClient, False),
    ("activity_log", ActivityLogPrimaryAdapterNATS, ActivityLogSecondaryAdapterNATSClient, False),
    ("coding_environment", CodingEnvironmentPrimaryAdapterNATS, CodingEnvironmentSecondaryAdapterNATSClient, False),
    ("events", EventPrimaryAdapterNATS, EventSecondaryAdapterNATSClient, True),
    ("source_control", SourceControlPrimaryAdapterNATS, SourceControlSecondaryAdapterNATSClient, False),
    ("vector_store", VectorStorePrimaryAdapterNATS, VectorStoreSecondaryAdapterNATSClient, True),
    ("triple_store", TripleStorePrimaryAdapterNATS, TripleStoreSecondaryAdapterNATSClient, False),
]

_ALL_FLAGS = [name for name, *_ in _WIRED_SERVICES]


def _services(available: dict[str, object] | None = None) -> MagicMock:
    """A MagicMock IEngine.Services with every ``<x>_available()`` defaulted
    to False. Pass e.g. ``{"object_storage": True}`` or
    ``{"object_storage": some_client_instance}`` to mark a service loaded --
    a bool just gets a fresh MagicMock adapter, anything else is used as
    the adapter directly (e.g. a real client instance, to test the
    re-exposure guard)."""
    available = available or {}
    services = MagicMock()
    for flag in _ALL_FLAGS:
        getattr(services, f"{flag}_available").return_value = flag in available
        value = available.get(flag)
        adapter = MagicMock() if value is True else value
        if adapter is not None:
            getattr(services, flag).adapter = adapter
    return services


def test_expose_services_is_a_noop_without_nats_config(monkeypatch):
    loader = EngineNATSLoader(SimpleNamespace(nats=None))
    connect = MagicMock()
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.get_connection", connect)

    started = loader.expose_services(_services({"object_storage": True}))

    assert started == []
    connect.assert_not_called()


def test_expose_services_is_a_noop_when_nothing_was_loaded(monkeypatch):
    config = SimpleNamespace(nats=NATSConfiguration(jwt_secret="x" * 32))
    loader = EngineNATSLoader(config)
    monkeypatch.setattr(
        "naas_abi_core.engine.nats_runtime.get_connection", MagicMock()
    )
    run_coro = MagicMock(side_effect=lambda coro, *a, **k: coro.close())
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.run_coro", run_coro)

    started = loader.expose_services(_services())

    assert started == []
    run_coro.assert_not_called()


@pytest.mark.parametrize(
    "flag,primary_cls,client_cls,wraps_raw_adapter", _WIRED_SERVICES
)
def test_expose_services_starts_a_primary_adapter_for_each_wired_service(
    monkeypatch, flag, primary_cls, client_cls, wraps_raw_adapter
):
    config = SimpleNamespace(
        nats=NATSConfiguration(nats_url="nats://example:4222", jwt_secret="x" * 32)
    )
    loader = EngineNATSLoader(config)
    fake_nc = MagicMock()
    get_connection = MagicMock(return_value=fake_nc)
    run_coro = MagicMock(side_effect=lambda coro, *a, **k: coro.close())
    monkeypatch.setattr(
        "naas_abi_core.engine.nats_runtime.get_connection", get_connection
    )
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.run_coro", run_coro)

    services = _services({flag: True})
    started = loader.expose_services(services)

    get_connection.assert_called_once_with("nats://example:4222")
    assert len(started) == 1
    primary = started[0]
    assert isinstance(primary, primary_cls)
    expected_wrapped = (
        getattr(services, flag).adapter if wraps_raw_adapter else getattr(services, flag)
    )
    assert primary._adapter is expected_wrapped
    run_coro.assert_called_once()


@pytest.mark.parametrize(
    "flag,primary_cls,client_cls,wraps_raw_adapter", _WIRED_SERVICES
)
def test_expose_services_does_not_re_expose_a_remote_client(
    monkeypatch, flag, primary_cls, client_cls, wraps_raw_adapter
):
    config = SimpleNamespace(nats=NATSConfiguration(jwt_secret="x" * 32))
    loader = EngineNATSLoader(config)
    monkeypatch.setattr(
        "naas_abi_core.engine.nats_runtime.get_connection", MagicMock()
    )
    run_coro = MagicMock(side_effect=lambda coro, *a, **k: coro.close())
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.run_coro", run_coro)

    remote_client = MagicMock(spec=client_cls)
    services = _services({flag: remote_client})

    started = loader.expose_services(services)

    assert started == []
    run_coro.assert_not_called()


def test_expose_services_starts_one_primary_per_available_service(monkeypatch):
    """Every wired service loaded at once -- the realistic boot scenario."""
    config = SimpleNamespace(
        nats=NATSConfiguration(nats_url="nats://example:4222", jwt_secret="x" * 32)
    )
    loader = EngineNATSLoader(config)
    monkeypatch.setattr(
        "naas_abi_core.engine.nats_runtime.get_connection", MagicMock()
    )
    run_coro = MagicMock(side_effect=lambda coro, *a, **k: coro.close())
    monkeypatch.setattr("naas_abi_core.engine.nats_runtime.run_coro", run_coro)

    services = _services({flag: True for flag in _ALL_FLAGS})
    started = loader.expose_services(services)

    assert len(started) == len(_WIRED_SERVICES)
    started_types = {type(p) for p in started}
    assert started_types == {primary_cls for _, primary_cls, _, _ in _WIRED_SERVICES}
