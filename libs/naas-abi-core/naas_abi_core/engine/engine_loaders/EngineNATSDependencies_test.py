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
