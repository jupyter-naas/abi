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


def test_a_slides_template_source_survives_the_trip_into_nexus_settings() -> None:
    """The stanza in config.yaml has to arrive at the slides resolver.

    NexusConfig is model_dump'd into the Nexus Settings, and both forbid extra
    keys, so a field declared on one side and not the other fails the boot on
    a config file that reads as correct. Walking the actual route is the only
    way to catch that; asserting the field exists on either model would not.
    """
    from naas_abi.apps.nexus.apps.api.app.core.config import Settings

    dumped = NexusConfig(
        slides_template_sources=[{"namespace": "acme", "path": "src/acme/templates"}]
    ).model_dump(exclude_none=True)

    settings = Settings(**dumped)

    (source,) = settings.slides_template_sources
    assert source.namespace == "acme"
    assert source.path == "src/acme/templates"


def test_a_slides_template_source_cannot_claim_the_abi_namespace() -> None:
    """Refused on the boot, before a picker can serve the wrong deck.

    The reserved name is checked once, in the Nexus Settings, rather than in
    both models. NexusConfig mirrors the shape of config.yaml and Settings
    owns what the values may be, so a second copy here would be a second
    place for the reserved name to drift out of step.
    """
    from naas_abi.apps.nexus.apps.api.app.core.config import Settings

    dumped = NexusConfig(
        slides_template_sources=[{"namespace": "abi", "path": "src/x/templates"}]
    ).model_dump(exclude_none=True)

    with pytest.raises(ValidationError, match="reserved"):
        Settings(**dumped)


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


def _default_module(registry: ModelRegistryService) -> ABIModule:
    engine = SimpleNamespace(
        services=SimpleNamespace(
            model_registry=registry,
            model_registry_available=lambda: True,
        )
    )
    return ABIModule(
        engine,  # type: ignore[arg-type]
        ABIModule.Configuration(global_config=GlobalConfig(ai_mode="cloud")),
    )


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


def test_boot_ships_no_slides_model_of_its_own(
    _restore_module_instance: None,
) -> None:
    """A bare ABI must not fail the check on ABI's own default.

    The default was anthropic/claude-sonnet-5, and the only module that
    registers that canonical id ships with a downstream application, not with
    ABI. So the shipped configuration could not satisfy the shipped check:
    every ABI boot without that application on the path raised against an
    empty registry, naming a setting nobody had edited. The registry here is
    empty on purpose, which is exactly the state an ABI checkout with no model
    modules enabled boots in.
    """
    _default_module(ModelRegistryService()).on_initialized()


def test_boot_keeps_a_configured_and_registered_slides_model(
    _restore_module_instance: None,
) -> None:
    """Naming a slides model still routes slides onto it.

    The optional default is only safe if the configured path is untouched.
    The install that found this sets abi_slides_agent_model while its general
    agent model is a free Gemma, so a fallback silently winning there would
    put every deck back on the model that produced template filler.
    """
    from langchain_openai import ChatOpenAI
    from naas_abi_core.models.Model import ChatModel

    from naas_abi.agents.slides import resolve_slides_llm_model

    registry = ModelRegistryService()
    registry.register(
        "anthropic/claude-sonnet-5",
        ChatModel(
            model_id="anthropic/claude-sonnet-5",
            provider="openrouter",
            model=ChatOpenAI(model="anthropic/claude-sonnet-5", api_key="sk-or-test"),  # type: ignore[arg-type]
        ),
    )
    module = _module(registry, "anthropic/claude-sonnet-5")
    module.on_initialized()

    assert resolve_slides_llm_model("gpt-4.1-mini") == "anthropic/claude-sonnet-5"
