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
from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
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


def test_coding_environment_configuration_coder_requires_admin_token():
    with pytest.raises(Exception):
        CodingEnvironmentAdapterConfiguration(
            adapter="coder",
            config={
                "access_url": "https://coder.example.com",
                "wildcard_access_url": "*.coder.example.com",
            },
        )
