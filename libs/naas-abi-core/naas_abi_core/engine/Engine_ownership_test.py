"""Engine.load and shutdown with the ownership lease (NATS mode)."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from naas_abi_core.engine.nats_sessions import SessionHost
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


class SessionPrimary(SessionHost):
    """A primary that owns sessions (transfers, streams), recording its handover."""

    def __init__(self, order: list[str], *, stuck: bool = False):
        self.order, self.stuck = order, stuck

    async def stop_accepting(self) -> None:
        self.order.append("stop_accepting")

    async def sessions_finished(self) -> None:
        self.order.append("sessions_finished")
        if self.stuck:
            await asyncio.Event().wait()

    async def stop(self) -> None:
        self.order.append("stop_sessions")


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
    # A client engine's agent memory is the serving engine's: no broker here.
    monkeypatch.setattr(
        "naas_abi_core.services.agent.DocumentCheckpointSaver.DocumentCheckpointSaver.setup",
        lambda self: None,
    )
    return found


def new_engine(**engine):
    from naas_abi_core.engine.Engine import Engine

    if not engine:
        return Engine(CONFIG)
    settings = ", ".join(f"{key}: {value}" for key, value in engine.items())
    return Engine(
        CONFIG.replace(
            "{jwt_secret: test-secret}",
            f"{{jwt_secret: test-secret, engine: {{{settings}}}}}",
        )
    )


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


def test_a_client_engine_reaches_every_service_through_nats_and_loads_none(
    parts, monkeypatch
):
    from naas_abi_core.engine.context import get_default_agent_checkpointer
    from naas_abi_core.engine.engine_loaders.EngineServiceLoader import (
        EngineServiceLoader,
    )
    from naas_abi_core.engine.nats_rpc import NatsRPCClient
    from naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter import (
        NATSJetStreamAdapter,
    )
    from naas_abi_core.services.model_registry.adapters.secondary.model_registry_client import (
        ModelRegistryNATSClient,
    )

    monkeypatch.setattr(
        EngineServiceLoader,
        "load_services",
        MagicMock(side_effect=AssertionError("a client engine loads no service")),
    )
    parts.claim.return_value = None
    engine = new_engine()

    engine.load()

    services = engine.services
    for name in (
        "object_storage",
        "document",
        "dataset",
        "kv",
        "email",
        "activity_log",
        "coding_environment",
        "source_control",
        "vector_store",
        "events",
        "triple_store",
    ):
        assert isinstance(getattr(services, name).adapter, NatsRPCClient), name
    assert all(isinstance(a, NatsRPCClient) for a in services.secret.adapters)
    assert all(isinstance(a, NatsRPCClient) for _, a in services.cache.adapters)
    assert isinstance(services.bus.adapter, NATSJetStreamAdapter)
    assert isinstance(services.model_registry, ModelRegistryNATSClient)
    # Agents keep their memory in the serving engine's document service.
    memory = get_default_agent_checkpointer()
    assert isinstance(memory.documents.adapter, NatsRPCClient)
    parts.expose.assert_not_called()
    engine.shutdown()


def test_a_client_engine_leaves_the_ontologies_to_the_serving_engine(
    parts, monkeypatch
):
    from naas_abi_core.engine.engine_loaders.EngineOntologyLoader import (
        EngineOntologyLoader,
    )

    load_ontologies = MagicMock()
    monkeypatch.setattr(EngineOntologyLoader, "load_ontologies", load_ontologies)
    parts.claim.return_value = None
    engine = new_engine()
    engine.configuration.global_config.skip_ontology_loading = False

    engine.load()

    load_ontologies.assert_not_called()
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


def test_the_lease_and_the_sessions_carry_the_engine_instance_id(parts, monkeypatch):
    from naas_abi_core.engine.engine_loaders.EngineOwnershipLoader import (
        EngineOwnershipLoader,
    )
    from naas_abi_core.engine.nats_transfer import TransferHost

    loaders: list[EngineOwnershipLoader] = []

    def claim(self):
        loaders.append(self)
        return Claim.STANDBY

    async def no_frames(*args):
        if False:
            yield b""

    hosts: list[TransferHost] = []

    def expose(services):
        hosts.append(TransferHost("t", "s", no_frames, operations=("get",)))
        return []

    monkeypatch.setattr(EngineOwnershipLoader, "claim", claim)
    parts.expose.side_effect = expose
    engine = new_engine()

    engine.load()
    start_serving = parts.take_over.call_args.args[0]
    start_serving()  # the standby took the lease

    assert loaders[0].holder.instance_id == engine.instance_id
    assert hosts[0].owner == engine.instance_id
    assert new_engine().instance_id != engine.instance_id
    engine.shutdown()


def test_shutdown_ends_the_shared_subjects_before_the_sessions(parts):
    parts.expose.side_effect = lambda services: [
        SessionPrimary(parts.order),
        primary(parts.order),
    ]
    engine = new_engine()
    engine.load()
    parts.order.clear()

    engine.shutdown()

    assert parts.order == [
        "stop_jobs",
        "release",
        "stop_accepting",
        "stop_primary",
        "sessions_finished",
        "sessions_finished",  # again: a call answered meanwhile may park its reply
        "stop_sessions",
        "close_lease",
    ]


def test_sessions_still_open_at_the_drain_deadline_are_closed(parts):
    parts.expose.side_effect = lambda services: [
        SessionPrimary(parts.order, stuck=True)
    ]
    engine = new_engine(drain_seconds=0.3)
    engine.load()
    parts.order.clear()

    started = time.monotonic()
    engine.shutdown()

    assert 0.3 <= time.monotonic() - started < 3
    assert parts.order[-2:] == ["stop_sessions", "close_lease"]


def test_fencing_closes_the_sessions_at_once(parts):
    parts.expose.side_effect = lambda services: [
        SessionPrimary(parts.order, stuck=True)
    ]
    engine = new_engine()
    engine.load()
    parts.order.clear()

    started = time.monotonic()
    parts.keep.call_args.kwargs["on_fenced"]()

    assert time.monotonic() - started < 1
    assert parts.order == ["stop_sessions"]
    engine.shutdown()


def test_without_drain_time_shutdown_closes_the_sessions_at_once(parts):
    parts.expose.side_effect = lambda services: [
        SessionPrimary(parts.order, stuck=True)
    ]
    engine = new_engine(drain_seconds=0)
    engine.load()
    parts.order.clear()

    engine.shutdown()

    assert parts.order == ["stop_jobs", "release", "stop_sessions", "close_lease"]
