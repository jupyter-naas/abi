"""How the API reaches the dataset service.

Inside Nexus the engine owns it. The dev server and the exporter can build one
directly, so the app can be run and rebuilt without the whole engine.
"""

from __future__ import annotations

import os
from functools import lru_cache

from naas_abi_core.services.dataset.DatasetService import DatasetService

# Matches the engine defaults in EngineConfiguration, so a dev server and a
# loaded module read the same warehouse unless told otherwise.
DEFAULT_CATALOG = "sqlite:storage/datasets.sqlite"
DEFAULT_DATA_PATH = "storage/datasets/"


@lru_cache(maxsize=1)
def standalone_service() -> DatasetService:
    """A dataset service for running this app without the engine."""
    from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory

    return DatasetFactory.DatasetServiceDuckLake(
        os.environ.get("DATASET_CATALOG", DEFAULT_CATALOG),
        os.environ.get("DATASET_DATA_PATH", DEFAULT_DATA_PATH),
    )


def dataset_service() -> DatasetService:
    """The engine's dataset service when a module is loaded, else a local one."""
    try:
        from naas_abi_marketplace.domains.personnel.apps.people import ABIModule

        module = ABIModule.get_instance()
    except Exception:  # noqa: BLE001 - not running inside the engine
        return standalone_service()
    if not module.engine.services.dataset_available():
        return standalone_service()
    return module.engine.services.dataset
