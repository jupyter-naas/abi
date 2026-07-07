import pytest

from naas_abi_core.engine.engine_configuration.EngineConfiguration_SourceControlService import (
    SourceControlAdapterConfiguration,
    SourceControlServiceConfiguration,
)
from naas_abi_core.services.source_control.adapters.secondary.ForgejoAdapter import (
    ForgejoAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
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


def test_source_control_configuration_forgejo_requires_admin_token():
    with pytest.raises(Exception):
        SourceControlAdapterConfiguration(
            adapter="forgejo",
            config={
                "base_url": "https://forge.example.com",
            },
        )
