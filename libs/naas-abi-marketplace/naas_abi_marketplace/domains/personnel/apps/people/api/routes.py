"""FastAPI routes for People Search.

The browser never queries the dataset service. It asks here, and this layer
decides what may be read: the table names, the namespace and the privacy rules
stay on the server.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from naas_abi_marketplace.domains.personnel.apps.people import profile_payload
from naas_abi_marketplace.domains.personnel.apps.people import (
    search_payload as search_module,
)
from naas_abi_marketplace.domains.personnel.apps.people.api.service import (
    dataset_service,
)
from naas_abi_marketplace.domains.personnel.apps.people.config_loader import (
    load_config,
    public_config,
)
from naas_abi_marketplace.domains.personnel.apps.people.datasets import (
    DatasetsMissingError,
)
from naas_abi_marketplace.domains.personnel.apps.people.ontology_payload import (
    build_ontology_payload,
)

router = APIRouter(tags=["personnel-people"])


@router.get("/config")
def get_config() -> dict:
    return public_config()


@router.get("/search")
def get_search(
    q: str = Query("", max_length=200),
    facet: str = Query("", max_length=120),
    page: int = Query(1, ge=1, le=1000),
) -> dict:
    try:
        return search_module.search(
            dataset_service(), load_config(), query=q, facet=facet, page=page
        )
    except DatasetsMissingError as exc:
        raise HTTPException(status_code=404, detail=exc.as_detail()) from exc


@router.get("/suggest")
def get_suggest(q: str = Query("", max_length=200)) -> dict:
    try:
        return {
            "suggestions": search_module.suggest(
                dataset_service(), load_config(), query=q
            )
        }
    except DatasetsMissingError as exc:
        raise HTTPException(status_code=404, detail=exc.as_detail()) from exc


@router.get("/ontology")
def get_ontology() -> dict:
    return build_ontology_payload()


@router.get("/people/{slug}")
def get_person(slug: str) -> dict:
    config = load_config()
    service = dataset_service()
    try:
        payload = profile_payload.profile(service, config, slug=slug)
        payload["related"] = profile_payload.related(service, config, slug=slug)
        return payload
    except profile_payload.ProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"No profile for {slug}") from exc
    except DatasetsMissingError as exc:
        raise HTTPException(status_code=404, detail=exc.as_detail()) from exc
