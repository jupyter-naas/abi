from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import GlobalConfig
from naas_abi_core.module.Module import BaseModule
from naas_abi_core.services.model_registry.ModelRegistryPort import (
    DefaultModelNotResolvedError,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from pydantic import ValidationError

from naas_abi import ABIModule, NexusConfig


def test_nexus_config_rejects_legacy_cors_origins_str() -> None:
    with pytest.raises(ValidationError):
        NexusConfig(cors_origins_str="https://nexus.example.com")


def test_nexus_config_rejects_legacy_cors_origins() -> None:
    with pytest.raises(ValidationError):
        NexusConfig(cors_origins='["https://nexus.example.com"]')


@pytest.fixture
def _restore_module_instance() -> Iterator[None]:
    """Constructing a module registers it as the process-wide instance.

    ``configured_slides_model`` reads ``ABIModule.get_instance()``, so a test
    module left registered would hand its own throwaway configuration to every
    later test in the process.
    """
    previous = BaseModule._instances.get(ABIModule)
    try:
        yield
    finally:
        if previous is None:
            BaseModule._instances.pop(ABIModule, None)
        else:
            BaseModule._instances[ABIModule] = previous


def _module(registry: ModelRegistryService, slides_model: str) -> ABIModule:
    engine = SimpleNamespace(
        services=SimpleNamespace(
            model_registry=registry,
            model_registry_available=lambda: True,
        )
    )
    return ABIModule(
        engine,  # type: ignore[arg-type]
        ABIModule.Configuration(
            global_config=GlobalConfig(ai_mode="cloud"),
            abi_slides_agent_model=slides_model,
        ),
    )


def test_boot_refuses_an_unregistered_slides_model(
    _restore_module_instance: None,
) -> None:
    """A slides model that does not resolve must stop the API starting.

    Slides no longer honour the model the client selected, so this one id is
    the only model any slides turn can run on. Left to fail at request time it
    fails on the twentieth deck, in front of a user, with the same absence of a
    log line that made the previous model bug cost a session.
    """
    module = _module(ModelRegistryService(), "anthropic/claude-sonnet-5-typo")

    with pytest.raises(DefaultModelNotResolvedError, match="claude-sonnet-5-typo"):
        module.on_initialized()
