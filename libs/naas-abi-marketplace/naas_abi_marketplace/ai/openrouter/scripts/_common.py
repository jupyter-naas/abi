"""Shared helpers for OpenRouter integration CLI scripts."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.module.Module import BaseModule
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)

load_dotenv()

MODULE_NAME = "naas_abi_marketplace.applications.openrouter"


def _try_get_openrouter_module() -> BaseModule | None:
    from naas_abi_marketplace.applications.openrouter import ABIModule

    try:
        return ABIModule.get_instance()
    except ValueError:
        return None


def _load_engine(module_names: list[str] | None = None) -> Engine:
    engine = Engine()
    if module_names:
        engine.load(module_names=module_names)
    else:
        engine.load()
    return engine


def _load_object_storage() -> ObjectStorageService:
    configuration = EngineConfiguration.load_configuration()
    return configuration.services.object_storage.load()


def ensure_module_loaded() -> BaseModule | None:
    """Return the OpenRouter module when it is enabled in config, else None."""
    module = _try_get_openrouter_module()
    if module is not None:
        return module

    _load_engine(module_names=[MODULE_NAME])
    return _try_get_openrouter_module()


def get_integration():
    """Build a wired :class:`OpenRouterAPIIntegration` from config or env."""
    from naas_abi_marketplace.ai.openrouter.integrations.OpenRouterAPIIntegration import (
        OpenRouterAPIIntegration,
        OpenRouterAPIIntegrationConfiguration,
    )

    module = ensure_module_loaded()
    if module is not None:
        configuration = OpenRouterAPIIntegrationConfiguration(
            api_key=module.configuration.openrouter_api_key,
            object_storage=module.engine.services.object_storage,
            datastore_path=module.configuration.datastore_path,
        )
        return OpenRouterAPIIntegration(configuration)

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            f"{MODULE_NAME} is not enabled in config.yaml and "
            "OPENROUTER_API_KEY is not set in the environment."
        )

    configuration = OpenRouterAPIIntegrationConfiguration(
        api_key=api_key,
        object_storage=_load_object_storage(),
        datastore_path="openrouter",
    )
    return OpenRouterAPIIntegration(configuration)
