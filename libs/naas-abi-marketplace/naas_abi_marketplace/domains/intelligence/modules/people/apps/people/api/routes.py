"""FastAPI routes for People Search.

The browser never queries the dataset service. It asks here, and this layer
decides what may be read: the table names, the namespace and the privacy rules
stay on the server.

``build_router`` binds a router to one ``config.yaml``. That is what makes a
second instance possible: two modules can mount two routers, with two brands
and two sets of tables, in the same process. ``router`` is the one bound to the
config shipped beside this package.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from naas_abi_marketplace.domains.personnel.apps.people.api.service import (
    dataset_service,
)
from naas_abi_marketplace.domains.personnel.apps.people.config_loader import (
    load_config,
    public_config,
)
from naas_abi_marketplace.domains.personnel.apps.people.scripts import profile_payload
from naas_abi_marketplace.domains.personnel.apps.people.scripts import (
    search_payload as search_module,
)
from naas_abi_marketplace.domains.personnel.apps.people.scripts.datasets import (
    DatasetsMissingError,
)
from naas_abi_marketplace.domains.personnel.apps.people.scripts.graph_view import (
    graph_view,
    graph_view_css,
)
from naas_abi_marketplace.domains.personnel.apps.people.scripts.ontology_payload import (
    build_ontology_payload,
)
from naas_abi_marketplace.domains.personnel.apps.people.scripts.sparql_execute import (
    CONTACT_VARIABLES,
    SparqlExecutionError,
    execute_profile_query,
)


def build_router(config_path: Path | None = None) -> APIRouter:
    """Routes reading one instance's configuration."""
    router = APIRouter(tags=["personnel-people"])

    def config() -> dict:
        return load_config(config_path)

    @router.get("/config")
    def get_config() -> dict:
        return public_config(config_path)

    @router.get("/search")
    def get_search(
        q: str = Query("", max_length=200),
        facet: str = Query("", max_length=120),
        page: int = Query(1, ge=1, le=1000),
    ) -> dict:
        try:
            return search_module.search(
                dataset_service(), config(), query=q, facet=facet, page=page
            )
        except DatasetsMissingError as exc:
            raise HTTPException(status_code=404, detail=exc.as_detail()) from exc

    @router.get("/suggest")
    def get_suggest(q: str = Query("", max_length=200)) -> dict:
        try:
            return {
                "suggestions": search_module.suggest(
                    dataset_service(), config(), query=q
                )
            }
        except DatasetsMissingError as exc:
            raise HTTPException(status_code=404, detail=exc.as_detail()) from exc

    @router.get("/ontology")
    def get_ontology() -> dict:
        return build_ontology_payload()

    @router.get("/people/{slug}")
    def get_person(slug: str) -> dict:
        settings = config()
        service = dataset_service()
        try:
            payload = profile_payload.profile(service, settings, slug=slug)
            payload["related"] = profile_payload.related(service, settings, slug=slug)
            return payload
        except profile_payload.ProfileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail=f"No profile for {slug}"
            ) from exc
        except DatasetsMissingError as exc:
            raise HTTPException(status_code=404, detail=exc.as_detail()) from exc

    @router.get("/people/{slug}/graph")
    def get_person_graph(slug: str) -> dict:
        """The cockpit graph page's data, run live on this instance's graph."""
        try:
            return graph_view(dataset_service(), config(), slug=slug)
        except profile_payload.ProfileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail=f"No profile for {slug}"
            ) from exc
        except DatasetsMissingError as exc:
            raise HTTPException(status_code=404, detail=exc.as_detail()) from exc

    @router.get("/graph-view.css")
    def get_graph_view_css() -> Response:
        return Response(graph_view_css(), media_type="text/css")

    @router.get("/people/{slug}/queries/{query_name}/run")
    def run_person_query(
        slug: str,
        query_name: str,
        max_rows: int = Query(50, ge=1, le=200),
    ) -> dict:
        settings = config()
        try:
            profile_payload.profile(dataset_service(), settings, slug=slug)
        except profile_payload.ProfileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail=f"No profile for {slug}"
            ) from exc
        except DatasetsMissingError as exc:
            raise HTTPException(status_code=404, detail=exc.as_detail()) from exc

        try:
            return execute_profile_query(
                query_name,
                slug,
                max_rows=max_rows,
                graph_file=settings["data"]["graph"]["file"],
                hidden_columns=()
                if settings["privacy"].get("publish_contact_details")
                else CONTACT_VARIABLES,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SparqlExecutionError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return router


router = build_router()
