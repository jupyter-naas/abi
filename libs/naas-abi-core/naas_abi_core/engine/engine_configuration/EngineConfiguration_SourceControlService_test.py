import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration_SourceControlService import (
    SourceControlAdapterConfiguration,
    SourceControlAdapterNATSConfiguration,
    SourceControlServiceConfiguration,
)
from naas_abi_core.services.source_control.adapters.secondary.ForgejoAdapter import (
    ForgejoAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.LocalGitAdapter import (
    LocalGitAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.SourceControlSecondaryAdapterNATSClient import (
    SourceControlSecondaryAdapterNATSClient,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    ISourceControlAdapter,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)


def test_source_control_configuration_forgejo_adapter():
    configuration = SourceControlServiceConfiguration(
        source_control_adapter=SourceControlAdapterConfiguration(
            adapter="forgejo",
            config={
                "base_url": "https://forge.example.com",
                "admin_token": "admin-token",
            },
        )
    )

    adapter = configuration.source_control_adapter.load()
    assert isinstance(adapter, ForgejoAdapter)
    assert isinstance(configuration.load(), SourceControlService)


def test_source_control_configuration_in_memory_adapter():
    configuration = SourceControlServiceConfiguration(
        source_control_adapter=SourceControlAdapterConfiguration(
            adapter="in_memory",
            config={},
        )
    )

    adapter = configuration.source_control_adapter.load()
    assert isinstance(adapter, InMemoryAdapter)
    assert isinstance(configuration.load(), SourceControlService)


def test_source_control_configuration_local_git_adapter(tmp_path):
    configuration = SourceControlServiceConfiguration(
        source_control_adapter=SourceControlAdapterConfiguration(
            adapter="local_git",
            config={"repos_root": str(tmp_path / "git")},
        )
    )

    adapter = configuration.source_control_adapter.load()
    assert isinstance(adapter, LocalGitAdapter)
    assert isinstance(configuration.load(), SourceControlService)


def test_source_control_configuration_forgejo_requires_admin_token():
    with pytest.raises(Exception):
        SourceControlAdapterConfiguration(
            adapter="forgejo",
            config={
                "base_url": "https://forge.example.com",
            },
        )


def test_source_control_configuration_nats_rpc_is_lazy():
    """Loading the "nats_rpc" adapter must construct the client without any
    network I/O -- SourceControlSecondaryAdapterNATSClient connects lazily on
    first use, so this must succeed with no live NATS server."""
    configuration = SourceControlServiceConfiguration(
        source_control_adapter=SourceControlAdapterConfiguration(
            adapter="nats_rpc",
            config={
                "nats_url": "nats://127.0.0.1:4222",
                "jwt_secret": "test-shared-secret",
                "service_identity": "api",
            },
        )
    )

    adapter = configuration.source_control_adapter.load()
    assert isinstance(adapter, ISourceControlAdapter)
    assert isinstance(adapter, SourceControlSecondaryAdapterNATSClient)
    assert isinstance(configuration.load(), SourceControlService)


def test_source_control_configuration_nats_rpc_requires_jwt_secret():
    with pytest.raises(Exception):
        SourceControlAdapterConfiguration(
            adapter="nats_rpc",
            config={"nats_url": "nats://127.0.0.1:4222"},
        )


def test_source_control_adapter_nats_configuration_rejects_unknown_fields():
    with pytest.raises(Exception):
        SourceControlAdapterNATSConfiguration(
            jwt_secret="test-shared-secret", unknown_field="x"
        )
