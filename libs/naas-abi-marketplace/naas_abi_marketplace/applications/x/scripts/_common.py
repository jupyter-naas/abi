"""Shared helpers for X integration CLI scripts."""

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
from naas_abi_core.utils.StorageUtils import StorageUtils

load_dotenv()
# Also pick up secrets from the vendored ABI workspace when run from axi-ai root.
load_dotenv(".abi/.env", override=False)


MODULE_NAME = "naas_abi_marketplace.applications.x"
DEFAULT_BASE_URL = "https://api.twitter.com/2"
DEFAULT_DATASTORE_PATH = "x"


def _token_from_env() -> str | None:
    token = os.environ.get("X_BEARER_TOKEN")
    if token and token.strip():
        return token.strip()
    return None


def _try_get_x_module() -> BaseModule | None:
    from naas_abi_marketplace.applications.x import ABIModule

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


def ensure_module_loaded() -> BaseModule | None:
    """Return the X module when it is enabled in config, else None."""
    module = _try_get_x_module()
    if module is not None:
        return module

    _load_engine(module_names=[MODULE_NAME])
    return _try_get_x_module()


def get_bearer_token() -> str:
    """Resolve the X bearer token from the environment or loaded module config."""
    token = _token_from_env()
    if token:
        return token

    module = ensure_module_loaded()
    if module is not None:
        module_token = module.configuration.bearer_token
        if isinstance(module_token, str) and module_token.strip():
            return module_token.strip()

    raise ValueError(
        "X_BEARER_TOKEN is not set in the environment and "
        f"{MODULE_NAME} could not be loaded from config.yaml."
    )


def _load_object_storage() -> ObjectStorageService:
    configuration = EngineConfiguration.load_configuration()
    return configuration.services.object_storage.load()


def get_datastore_path() -> str:
    """Return the X module datastore prefix, defaulting to ``x``."""
    module = _try_get_x_module()
    if module is not None:
        path = module.configuration.datastore_path
        if isinstance(path, str) and path.strip():
            return path.strip()
    return DEFAULT_DATASTORE_PATH


def save_diagnostic_report(*, markdown: str, report: dict) -> dict[str, str]:
    """Persist diagnostic artifacts under ``<datastore>/diagnostic/<ts>_diagnostic.*``.

    Returns:
        dict[str, str]: ``markdown`` and ``json`` object-storage paths.
    """
    import json
    from datetime import UTC, datetime

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    dir_path = f"{get_datastore_path()}/diagnostic"
    storage_utils = StorageUtils(_load_object_storage())

    markdown_name = f"{timestamp}_diagnostic.md"
    storage_utils.save_text(
        markdown,
        dir_path,
        markdown_name,
        copy=False,
    )

    json_name = f"{timestamp}_diagnostic.json"
    storage_utils.save_json(
        report,
        dir_path,
        json_name,
        copy=False,
    )

    return {
        "markdown": f"{dir_path}/{markdown_name}",
        "json": f"{dir_path}/{json_name}",
    }


def get_integration():
    """Build a wired :class:`XIntegration` from config or env."""
    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegration,
        XIntegrationConfiguration,
    )

    module = ensure_module_loaded()
    if module is not None:
        configuration = XIntegrationConfiguration(
            bearer_token=module.configuration.bearer_token,
            datastore_path=module.configuration.datastore_path,
        )
        return XIntegration(configuration)

    configuration = XIntegrationConfiguration(bearer_token=get_bearer_token())
    return XIntegration(configuration)


def token_fingerprint(token: str) -> str:
    """Return a short, non-secret identifier for the bearer token."""
    if len(token) <= 12:
        return "<redacted>"
    return f"{token[:4]}…{token[-4:]} (len={len(token)})"
