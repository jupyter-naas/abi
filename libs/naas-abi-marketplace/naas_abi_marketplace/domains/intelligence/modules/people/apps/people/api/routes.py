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

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.api.service import (
    dataset_service,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.config_loader import (
    load_config,
    public_config,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    profile_payload,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    search_payload as search_module,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.datasets import (
    DatasetsMissingError,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.graph_view import (
    graph_view,
    graph_view_css,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.memory_people_store import (
    PeopleStore,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.network_payload import (
    network as search_network,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.ontology_payload import (
    build_ontology_payload,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.people_resolver import (
    WORKSPACE_BACKENDS,
    resolve_sparql_snapshot,
    resolve_workspace_dataset,
    resolve_workspace_graph,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.sparql_execute import (
    CONTACT_VARIABLES,
    SparqlExecutionError,
    execute_profile_query,
)
from rdflib import Graph


def _bearer(request: Request) -> str:
    header = request.headers.get("Authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _authenticated_by_api_key(request: Request) -> object:
    expected = os.environ.get("ABI_API_KEY")
    if not expected or _bearer(request) != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "api-key"


def auth_dependency():
    try:
        from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
            get_current_user_required,
        )
    except ImportError:
        return _authenticated_by_api_key
    return get_current_user_required


def _viewer_id(auth: Any, current_user: Any) -> str | None:
    if auth is _authenticated_by_api_key:
        return None
    return str(getattr(current_user, "id", "") or "") or None


@dataclass(frozen=True)
class PeopleRequestContext:
    store: PeopleStore
    live_graph: Graph | None
    # Set when the store is a workspace's materialized dataset: the graphs it
    # was built from, read only by the pages that query triples: a profile's
    # graph and queries, and the network of a search.
    graph_iris: tuple[str, ...] = ()

    async def graph(self) -> Graph | None:
        if self.live_graph is not None:
            return self.live_graph
        if self.graph_iris:
            return await resolve_workspace_graph(self.graph_iris)
        return None


def build_router(config_path: Path | None = None) -> APIRouter:
    """Routes reading one instance's configuration."""
    router = APIRouter(tags=["people"])
    auth = auth_dependency()

    def config() -> dict:
        return load_config(config_path)

    async def _people_context(
        workspace_id: str | None = Query(None, max_length=100),
        current_user: Any = Depends(auth),
    ) -> PeopleRequestContext:
        settings = config()
        user_id = _viewer_id(auth, current_user)
        backend = settings["data"].get("backend")
        if (
            backend in WORKSPACE_BACKENDS
            and workspace_id
            and user_id is None
            and auth is not _authenticated_by_api_key
        ):
            raise HTTPException(status_code=401, detail="Authentication required")
        try:
            if backend == "workspace_dataset" and workspace_id and user_id:
                store, graph_iris = await resolve_workspace_dataset(
                    settings, workspace_id=workspace_id, user_id=user_id
                )
                return PeopleRequestContext(
                    store=store, live_graph=None, graph_iris=graph_iris
                )
            snapshot = await resolve_sparql_snapshot(
                settings, workspace_id=workspace_id, user_id=user_id
            )
        except DatasetsMissingError as exc:
            raise HTTPException(status_code=404, detail=exc.as_detail()) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if snapshot is None:
            return PeopleRequestContext(store=dataset_service(), live_graph=None)
        return PeopleRequestContext(store=snapshot.store, live_graph=snapshot.graph)

    @router.get("/config")
    def get_config() -> dict:
        return public_config(config_path)

    @router.get("/search")
    async def get_search(
        q: str = Query("", max_length=200),
        facet: str = Query("", max_length=120),
        page: int = Query(1, ge=1, le=1000),
        ctx: PeopleRequestContext = Depends(_people_context),
    ) -> dict:
        # In a thread: the routes share one event loop, and the page asks for
        # its search, suggestions and network at once.
        try:
            return await asyncio.to_thread(
                search_module.search,
                ctx.store,
                config(),
                query=q,
                facet=facet,
                page=page,
            )
        except DatasetsMissingError as exc:
            raise HTTPException(status_code=404, detail=exc.as_detail()) from exc

    @router.get("/search/network")
    async def get_search_network(
        q: str = Query("", max_length=200),
        facet: str = Query("", max_length=120),
        ctx: PeopleRequestContext = Depends(_people_context),
    ) -> dict:
        """The Network view: the query, what it matched and the people it leads to."""
        try:
            graph = await ctx.graph()
            return await asyncio.to_thread(
                search_network,
                ctx.store,
                config(),
                query=q,
                facet=facet,
                graph=graph,
            )
        except DatasetsMissingError as exc:
            raise HTTPException(status_code=404, detail=exc.as_detail()) from exc

    @router.get("/suggest")
    async def get_suggest(
        q: str = Query("", max_length=200),
        ctx: PeopleRequestContext = Depends(_people_context),
    ) -> dict:
        try:
            suggestions = await asyncio.to_thread(
                search_module.suggest, ctx.store, config(), query=q
            )
            return {"suggestions": suggestions}
        except DatasetsMissingError as exc:
            raise HTTPException(status_code=404, detail=exc.as_detail()) from exc

    @router.get("/ontology")
    def get_ontology() -> dict:
        return build_ontology_payload()

    @router.get("/people/{slug}")
    async def get_person(
        slug: str,
        ctx: PeopleRequestContext = Depends(_people_context),
    ) -> dict:
        settings = config()
        try:
            payload = profile_payload.profile(ctx.store, settings, slug=slug)
            payload["related"] = profile_payload.related(ctx.store, settings, slug=slug)
            return payload
        except profile_payload.ProfileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail=f"No profile for {slug}"
            ) from exc
        except DatasetsMissingError as exc:
            raise HTTPException(status_code=404, detail=exc.as_detail()) from exc

    @router.get("/people/{slug}/graph")
    async def get_person_graph(
        slug: str,
        ctx: PeopleRequestContext = Depends(_people_context),
    ) -> dict:
        """The person graph page's data, run live on this instance's graph."""
        settings = config()
        try:
            live_graph = await ctx.graph()
            if live_graph is not None:
                return graph_view(
                    ctx.store,
                    settings,
                    slug=slug,
                    live_graph=live_graph,
                )
            return graph_view(ctx.store, settings, slug=slug)
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
    async def run_person_query(
        slug: str,
        query_name: str,
        max_rows: int = Query(50, ge=1, le=200),
        ctx: PeopleRequestContext = Depends(_people_context),
    ) -> dict:
        settings = config()
        try:
            profile_payload.profile(ctx.store, settings, slug=slug)
        except profile_payload.ProfileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail=f"No profile for {slug}"
            ) from exc
        except DatasetsMissingError as exc:
            raise HTTPException(status_code=404, detail=exc.as_detail()) from exc

        graph_files = tuple(settings["data"]["graph"]["files"]) or None
        try:
            live_graph = await ctx.graph()
            return execute_profile_query(
                query_name,
                slug,
                max_rows=max_rows,
                graph_file=None if live_graph is not None else graph_files,
                graph=live_graph,
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
