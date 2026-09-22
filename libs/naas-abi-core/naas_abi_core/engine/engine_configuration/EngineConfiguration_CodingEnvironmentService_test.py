import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration_CodingEnvironmentService import (
    CodingEnvironmentAdapterConfiguration,
    CodingEnvironmentServiceConfiguration,
)
from naas_abi_core.services.coding_environment.adapters.secondary.CoderAdapter import (
    CoderAdapter,
)
from naas_abi_core.services.coding_environment.adapters.secondary.CodeServerComposeAdapter import (
    CodeServerComposeAdapter,
)
from naas_abi_core.services.coding_environment.adapters.secondary.CodingEnvironmentSecondaryAdapterNATSClient import (
    CodingEnvironmentSecondaryAdapterNATSClient,
)
from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.coding_environment.adapters.secondary.LocalDirectoryAdapter import (
    LocalDirectoryAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    ICodingEnvironmentAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)


def test_coding_environment_configuration_coder_adapter():
    configuration = CodingEnvironmentServiceConfiguration(
        coding_environment_adapter=CodingEnvironmentAdapterConfiguration(
            adapter="coder",
            config={
                "access_url": "https://coder.example.com",
                "wildcard_access_url": "*.coder.example.com",
                "admin_token": "admin-token",
                "workspace_autostop_ms": 1_800_000,
            },
        )
    )

    adapter = configuration.coding_environment_adapter.load()
    assert isinstance(adapter, CoderAdapter)
    assert isinstance(configuration.load(), CodingEnvironmentService)


def test_coding_environment_configuration_in_memory_adapter():
    configuration = CodingEnvironmentServiceConfiguration(
        coding_environment_adapter=CodingEnvironmentAdapterConfiguration(
            adapter="in_memory",
            config={},
        )
    )

    adapter = configuration.coding_environment_adapter.load()
    assert isinstance(adapter, InMemoryAdapter)
    assert isinstance(configuration.load(), CodingEnvironmentService)


def test_coding_environment_configuration_code_server_adapter():
    configuration = CodingEnvironmentServiceConfiguration(
        coding_environment_adapter=CodingEnvironmentAdapterConfiguration(
            adapter="code_server",
            config={"url": "https://code-server.example.com"},
        )
    )

    adapter = configuration.coding_environment_adapter.load()
    assert isinstance(adapter, CodeServerComposeAdapter)
    assert isinstance(configuration.load(), CodingEnvironmentService)


def test_coding_environment_configuration_local_directory_adapter(tmp_path):
    configuration = CodingEnvironmentServiceConfiguration(
        coding_environment_adapter=CodingEnvironmentAdapterConfiguration(
            adapter="local_directory",
            config={"workspaces_root": str(tmp_path / "workspaces")},
        )
    )

    adapter = configuration.coding_environment_adapter.load()
    assert isinstance(adapter, LocalDirectoryAdapter)
    assert isinstance(configuration.load(), CodingEnvironmentService)


def test_coding_environment_configuration_nats_rpc_adapter_is_lazy():
    """Loading the "nats_rpc" adapter must construct the client without any
    network I/O -- CodingEnvironmentSecondaryAdapterNATSClient connects
    lazily on first use, so this must succeed with no live NATS server."""
    configuration = CodingEnvironmentServiceConfiguration(
        coding_environment_adapter=CodingEnvironmentAdapterConfiguration(
            adapter="nats_rpc",
            config={
                "nats_url": "nats://127.0.0.1:4222",
                "jwt_secret": "test-shared-secret",
                "service_identity": "api",
            },
        )
    )

    adapter = configuration.coding_environment_adapter.load()
    assert isinstance(adapter, ICodingEnvironmentAdapter)
    assert isinstance(adapter, CodingEnvironmentSecondaryAdapterNATSClient)
    assert isinstance(configuration.load(), CodingEnvironmentService)


def test_coding_environment_configuration_coder_requires_admin_token():
    with pytest.raises(Exception):
        CodingEnvironmentAdapterConfiguration(
            adapter="coder",
            config={
                "access_url": "https://coder.example.com",
                "wildcard_access_url": "*.coder.example.com",
            },
        )
