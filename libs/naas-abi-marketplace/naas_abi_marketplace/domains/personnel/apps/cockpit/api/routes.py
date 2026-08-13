"""FastAPI routes for Personnel Cockpit datasets."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from naas_abi_marketplace.domains.personnel.apps.cockpit.api.storage import read_json

router = APIRouter(tags=["personnel-cockpit"])


@router.get("/globals/{name}")
def get_global(name: str) -> dict:
    try:
        return read_json(f"globals/{name}")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/entities/{entity_id}/{path:path}")
def get_entity_dataset(entity_id: str, path: str) -> dict:
    try:
        return read_json(f"entities/{entity_id}/{path}")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
