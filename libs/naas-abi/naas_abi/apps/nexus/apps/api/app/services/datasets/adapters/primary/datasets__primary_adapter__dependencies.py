from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from naas_abi.apps.nexus.apps.api.app.services.datasets.service import DatasetsService
from naas_abi_core.services.dataset.DatasetService import DatasetService


def get_dataset_service(request: Request) -> DatasetService | None:
    cached = getattr(request.app.state, "dataset_service", None)
    if cached is not None:
        return cached

    try:
        from naas_abi import ABIModule

        module = ABIModule.get_instance()
        if not module.engine.services.dataset_available():
            return None
        service = module.engine.services.dataset
        request.app.state.dataset_service = service
        return service
    except Exception as exc:  # pragma: no cover - runtime protection
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dataset service is not initialized. Load API through naas_abi.ABIModule.",
        ) from exc


def get_datasets_service(
    dataset: DatasetService | None = Depends(get_dataset_service),
) -> DatasetsService:
    return DatasetsService(dataset)
