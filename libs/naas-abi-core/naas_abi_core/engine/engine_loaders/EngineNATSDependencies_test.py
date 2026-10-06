from unittest.mock import MagicMock

from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineNATSDependencies import (
    EngineNATSDependencies,
)
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import (
    CacheFSAdapter,
)
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.adaptors.secondary.SecretSecondaryAdapterNATSClient import (
    SecretSecondaryAdapterNATSClient,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter


def test_domains_receive_only_network_dependencies_and_no_local_model_objects(tmp_path):
    local_storage = ObjectStorageService(MagicMock())
    local_kv = KeyValueService(MagicMock())
    owners = IEngine.Services(
        object_storage=local_storage,
        kv=local_kv,
        cache=CacheService(
            [
                ("hot", CacheFSAdapter(str(tmp_path / "hot"))),
                ("cold", CacheFSAdapter(str(tmp_path / "cold"))),
            ]
        ),
        model_registry=MagicMock(),
    )
    wiring = EngineNATSDependencies(NATSConfiguration(jwt_secret="x" * 32))
    dependencies = wiring.build(owners)
    try:
        owners.wire_services(dependencies)
        assert local_storage.services is dependencies
        assert local_kv.services is dependencies
        assert dependencies.object_storage is not local_storage
        assert dependencies.kv is not local_kv
        assert isinstance(dependencies.object_storage.adapter, NatsRPCClient)
        assert isinstance(dependencies.kv.adapter, NatsRPCClient)
        assert dependencies.model_registry_available()
        assert wiring.module_services.model_registry is not owners.model_registry
        assert wiring.module_services.model_registry.owner is owners.model_registry
        assert [tier for tier, _ in dependencies.cache.adapters] == ["hot", "cold"]
        assert all(
            isinstance(adapter, NatsRPCClient)
            for _, adapter in dependencies.cache.adapters
        )
        # Proxies for service-level endpoints must not emit the owner's events twice.
        assert not dependencies.object_storage.services_wired
        assert not dependencies.kv.services_wired
        assert not dependencies.cache.services_wired
    finally:
        wiring.close()
    assert not wiring.clients


def test_without_remote_view_local_wiring_is_unchanged():
    owners = IEngine.Services(kv=KeyValueService(MagicMock()))
    owners.wire_services()
    assert owners.kv.services is owners


def test_dependency_failure_has_no_local_fallback():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    import pytest

    local_backend = MagicMock()
    owner = ObjectStorageService(local_backend)
    wiring = EngineNATSDependencies(NATSConfiguration(jwt_secret="x" * 32))
    dependencies = wiring.build(IEngine.Services(object_storage=owner))
    try:
        adapter = dependencies.object_storage.adapter
        adapter._ensure_connection_async = AsyncMock(
            return_value=SimpleNamespace(max_payload=1024 * 1024)
        )
        adapter._call = MagicMock(side_effect=ConnectionError("unavailable"))
        adapter._open_transfer = MagicMock(side_effect=ConnectionError("unavailable"))
        for content in (b"value", b"x" * (64 * 1024 + 1)):
            with pytest.raises(ConnectionError):
                dependencies.object_storage.put_object("prefix", "key", content)
        adapter._call.assert_called_once()
        adapter._open_transfer.assert_called_once()
        local_backend.put_object.assert_not_called()
    finally:
        wiring.close()


def test_existing_remote_route_is_retained():
    from naas_abi_core.services.keyvalue.adapters.secondary.KeyValueSecondaryAdapterNATSClient import (
        KeyValueSecondaryAdapterNATSClient,
    )

    remote = KeyValueSecondaryAdapterNATSClient(
        "nats://upstream:4222", "x" * 32, "engine"
    )
    wiring = EngineNATSDependencies(NATSConfiguration(jwt_secret="x" * 32))
    try:
        dependencies = wiring.build(IEngine.Services(kv=KeyValueService(remote)))
        assert dependencies.kv.adapter is remote
    finally:
        wiring.close()


def test_facades_wait_as_long_as_the_configuration_says(tmp_path):
    from naas_abi_core.services.dataset.DatasetService import DatasetService
    from naas_abi_core.services.keyvalue.adapters.secondary.KeyValueSecondaryAdapterNATSClient import (
        KeyValueSecondaryAdapterNATSClient,
    )

    upstream = KeyValueSecondaryAdapterNATSClient(
        "nats://upstream:4222", "x" * 32, "engine", timeout_seconds=3.0
    )
    owners = IEngine.Services(
        object_storage=ObjectStorageService(MagicMock()),
        dataset=DatasetService(MagicMock()),
        kv=KeyValueService(upstream),
        secret=Secret([MagicMock(spec=ISecretAdapter)]),
        cache=CacheService([("hot", CacheFSAdapter(str(tmp_path / "hot")))]),
    )
    config = NATSConfiguration(jwt_secret="x" * 32, client_timeout_seconds=120)
    wiring = EngineNATSDependencies(config)
    try:
        dependencies = wiring.build(owners)

        built = [
            dependencies.object_storage.adapter,
            dependencies.dataset.adapter,
            *dependencies.secret.adapters,
            *(adapter for _, adapter in dependencies.cache.adapters),
        ]
        assert all(isinstance(client, NatsRPCClient) for client in built)
        assert {client._timeout_seconds for client in built} == {120.0}
        # A route configured to another engine keeps its own setting.
        assert dependencies.kv.adapter is upstream
        assert upstream._timeout_seconds == 3.0
    finally:
        wiring.close()


# --- secret fanout: the local part is this engine's, the remote part upstream's


def _upstream_secret() -> SecretSecondaryAdapterNATSClient:
    return SecretSecondaryAdapterNATSClient("nats://upstream:4222", "x" * 32, "engine")


def _secret_view(*adapters) -> tuple[EngineNATSDependencies, list]:
    wiring = EngineNATSDependencies(
        NATSConfiguration(nats_url="nats://engine:4222", jwt_secret="x" * 32)
    )
    dependencies = wiring.build(IEngine.Services(secret=Secret(list(adapters))))
    return wiring, dependencies.secret.adapters


def _is_own_endpoint(adapter) -> bool:
    return (
        isinstance(adapter, SecretSecondaryAdapterNATSClient)
        and adapter._nats_url == "nats://engine:4222"
    )


def test_a_local_secret_fanout_is_read_through_this_engines_endpoint():
    wiring, view = _secret_view(
        MagicMock(spec=ISecretAdapter), MagicMock(spec=ISecretAdapter)
    )
    try:
        assert len(view) == 1 and _is_own_endpoint(view[0])
    finally:
        wiring.close()


def test_a_remote_secret_fanout_keeps_its_upstream_routes():
    first, second = _upstream_secret(), _upstream_secret()
    wiring, view = _secret_view(first, second)
    try:
        assert view == [first, second]
    finally:
        wiring.close()


def test_a_mixed_secret_fanout_reads_locally_first_then_upstream():
    """Stage 1's ``[dotenv, nats_rpc]``: the local part is served by this engine,
    nats_rpc still reads upstream, in the configured order."""
    upstream = _upstream_secret()
    wiring, view = _secret_view(MagicMock(spec=ISecretAdapter), upstream)
    try:
        assert len(view) == 2
        assert _is_own_endpoint(view[0])
        assert view[1] is upstream
    finally:
        wiring.close()
    assert not wiring.clients


def test_a_mixed_secret_fanout_keeps_the_upstream_position():
    upstream = _upstream_secret()
    wiring, view = _secret_view(
        upstream, MagicMock(spec=ISecretAdapter), MagicMock(spec=ISecretAdapter)
    )
    try:
        assert len(view) == 2
        assert view[0] is upstream
        assert _is_own_endpoint(view[1])
    finally:
        wiring.close()


def test_a_mixed_secret_fanout_falls_through_to_upstream(monkeypatch):
    upstream = _upstream_secret()
    wiring = EngineNATSDependencies(NATSConfiguration(jwt_secret="x" * 32))
    try:
        dependencies = wiring.build(
            IEngine.Services(secret=Secret([MagicMock(spec=ISecretAdapter), upstream]))
        )
        own, _ = dependencies.secret.adapters
        monkeypatch.setattr(own, "get", lambda key, default=None: default)
        monkeypatch.setattr(upstream, "get", lambda key, default=None: f"up:{key}")

        assert dependencies.secret.get("TOKEN") == "up:TOKEN"
    finally:
        wiring.close()
