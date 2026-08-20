"""FastAPI routes for Personnel Cockpit datasets."""

from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, HTTPException
from naas_abi_marketplace.domains.personnel.apps.cockpit.api.storage import (
    MissingDatasetError,
    read_json,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.config_loader import (
    is_public_page,
    public_config,
)

router = APIRouter(tags=["personnel-cockpit"])


@router.get("/config")
def get_config() -> dict:
    return public_config()


@router.get("/globals/{name}")
def get_global(name: str) -> dict:
    try:
        return read_json(f"globals/{name}")
    except MissingDatasetError as exc:
        raise HTTPException(status_code=404, detail=exc.as_detail()) from exc


@router.get("/entities/{entity_id}/{path:path}")
def get_entity_dataset(entity_id: str, path: str) -> dict:
    page_id = path.split("/", 1)[0]
    if path != "manifest.json" and page_id and not is_public_page(page_id):
        raise HTTPException(status_code=403, detail=f"Page is not accessible: {page_id}")
    try:
        payload = read_json(f"entities/{entity_id}/{path}")
    except MissingDatasetError as exc:
        raise HTTPException(status_code=404, detail=exc.as_detail()) from exc
    if path == "manifest.json":
        payload = deepcopy(payload)
        pages = payload.get("datasets", {}).get("pages", {})
        payload["datasets"]["pages"] = {
            page: datasets for page, datasets in pages.items() if is_public_page(page)
        }
    return payload
