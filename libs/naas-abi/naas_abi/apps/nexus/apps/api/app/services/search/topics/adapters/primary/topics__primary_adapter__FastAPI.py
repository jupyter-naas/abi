"""HTTP routes for search topics, mounted under ``/api/search/topics``.

Reading (list, results, detail) needs workspace access; editing the topic
definitions and previewing raw templates needs a workspace owner or admin.
Every query runs through the workspace-scoped graph store, so a topic can only
ever read the graphs the workspace is allowed to read.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_workspace_role,
    require_workspace_access,
    require_workspace_admin,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
    GraphQuerySpecError,
    GraphServiceUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.adapters.secondary.graph_query__secondary_adapter__triplestore import (  # noqa: E501
    GraphQueryTripleStoreAdapter,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import IGraphQueryStore
from naas_abi.apps.nexus.apps.api.app.services.search.topics.adapters.secondary.postgres import (
    PostgresSearchTopicStore,
)
from naas_abi.apps.nexus.apps.api.app.services.search.topics.scope import topic_scope
from naas_abi.apps.nexus.apps.api.app.services.search.topics.service import SearchTopicService
from naas_abi.apps.nexus.apps.api.app.services.search.topics.topics__schema import (
    ROLE_CONTRACTS,
    SearchTopic,
    SearchTopicNotFoundError,
    SearchTopicValidationError,
)
from pydantic import BaseModel, Field

router = APIRouter()

_service = SearchTopicService(PostgresSearchTopicStore())


def get_search_topic_service() -> SearchTopicService:
    return _service


class TopicSectionIn(BaseModel):
    id: str
    label: str
    query: str
    empty_text: str = "Nothing recorded."
    link_topic: str | None = None


class TopicIn(BaseModel):
    label: str
    plural_label: str = ""
    description: str = ""
    icon: str = "Search"
    class_iri: str = ""
    results_query: str
    header_query: str
    sections: list[TopicSectionIn] = Field(default_factory=list)
    graphs: list[str] = Field(default_factory=list)
    enabled: bool = True
    order: int = 100


class PreviewIn(BaseModel):
    workspace_id: str
    role: str
    query: str
    params: dict[str, Any] = Field(default_factory=dict)
    graphs: list[str] = Field(default_factory=list)


async def _scoped_store(
    user_id: str, workspace_id: str, graphs: tuple[str, ...] | list[str] = ()
) -> IGraphQueryStore:
    """The workspace's readable graphs, narrowed to ``graphs`` when a topic names some."""
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.primary.graph__primary_adapter__dependencies import (  # noqa: E501
        workspace_graph_service,
    )
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.scoped_store import (
        WorkspaceGraphStore,
    )
    from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry

    graph = await workspace_graph_service(ServiceRegistry.instance().graph, user_id, workspace_id)
    assert graph.access_scope is not None
    scope = topic_scope(graph.access_scope, graphs)
    return GraphQueryTripleStoreAdapter(WorkspaceGraphStore(graph._get_catalog_store(), scope))


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HTTPException):  # workspace access checks already chose their status
        return exc
    if isinstance(exc, SearchTopicValidationError):
        return HTTPException(status_code=422, detail={"errors": exc.errors})
    if isinstance(exc, SearchTopicNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, GraphAccessError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, GraphQuerySpecError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, GraphServiceUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=502, detail=f"Topic query failed: {exc}")


@router.get("/contract")
async def get_contract() -> dict[str, Any]:
    """The placeholders and variables each query role accepts (for the settings editor)."""
    return {
        role: {
            "placeholders": sorted(c.placeholders),
            "required": sorted(c.required),
            "optional": sorted(c.optional),
            "extra_as_facts": c.extra_as_facts,
        }
        for role, c in ROLE_CONTRACTS.items()
    }


@router.get("")
async def list_topics(
    workspace_id: str = Query(...),
    current_user=Depends(get_current_user_required),
    service: SearchTopicService = Depends(get_search_topic_service),
) -> dict[str, Any]:
    await require_workspace_access(current_user.id, workspace_id)
    role = await get_workspace_role(current_user.id, workspace_id)
    topics = await service.list_topics(workspace_id)
    return {
        "topics": [t.to_dict() for t in topics],
        "disabled_scopes": sorted(await service.disabled_scopes(workspace_id)),
        "can_edit": role in ("owner", "admin"),
    }


class ScopeEnabledIn(BaseModel):
    enabled: bool


@router.put("/scopes/{scope_id}")
async def set_scope_enabled(
    scope_id: str,
    body: ScopeEnabledIn,
    workspace_id: str = Query(...),
    current_user=Depends(get_current_user_required),
    service: SearchTopicService = Depends(get_search_topic_service),
) -> dict[str, Any]:
    """Switch a Nexus feature or a web engine on or off in this workspace's search."""
    await require_workspace_admin(current_user.id, workspace_id)
    try:
        disabled = await service.set_scope_enabled(
            workspace_id, scope_id, body.enabled, user_id=current_user.id
        )
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"disabled_scopes": sorted(disabled)}


@router.post("/preview")
async def preview_query(
    body: PreviewIn,
    current_user=Depends(get_current_user_required),
    service: SearchTopicService = Depends(get_search_topic_service),
) -> dict[str, Any]:
    await require_workspace_admin(current_user.id, body.workspace_id)
    if body.role not in ROLE_CONTRACTS:
        raise HTTPException(status_code=422, detail={"errors": [f"unknown role {body.role!r}"]})
    store = await _scoped_store(current_user.id, body.workspace_id, body.graphs)
    try:
        sparql, rows = await service.preview(body.query, body.role, body.params, store)
    except Exception as exc:
        raise _http_error(exc) from exc
    return {
        "sparql": sparql,
        "rows": [{k: asdict(v) for k, v in row.items()} for row in rows],
    }


@router.get("/{topic_id}/results")
async def topic_results(
    topic_id: str,
    workspace_id: str = Query(...),
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
    current_user=Depends(get_current_user_required),
    service: SearchTopicService = Depends(get_search_topic_service),
) -> dict[str, Any]:
    try:
        topic = await service.get_topic(workspace_id, topic_id)
        store = await _scoped_store(current_user.id, workspace_id, topic.graphs)
        results = await service.search(workspace_id, topic_id, q, store, limit=limit, offset=offset)
    except Exception as exc:
        raise _http_error(exc) from exc
    return asdict(results)


@router.get("/{topic_id}/detail")
async def topic_detail(
    topic_id: str,
    workspace_id: str = Query(...),
    uri: str = Query(..., min_length=1, max_length=2048),
    current_user=Depends(get_current_user_required),
    service: SearchTopicService = Depends(get_search_topic_service),
) -> dict[str, Any]:
    try:
        topic = await service.get_topic(workspace_id, topic_id)
        store = await _scoped_store(current_user.id, workspace_id, topic.graphs)
        detail = await service.detail(workspace_id, topic_id, uri, store)
    except Exception as exc:
        raise _http_error(exc) from exc
    return asdict(detail)


@router.put("/{topic_id}")
async def save_topic(
    topic_id: str,
    body: TopicIn,
    workspace_id: str = Query(...),
    current_user=Depends(get_current_user_required),
    service: SearchTopicService = Depends(get_search_topic_service),
) -> dict[str, Any]:
    await require_workspace_admin(current_user.id, workspace_id)
    topic = SearchTopic.from_dict({**body.model_dump(), "id": topic_id})
    try:
        saved = await service.save_topic(workspace_id, topic, user_id=current_user.id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return saved.to_dict()


@router.delete("/{topic_id}")
async def reset_topic(
    topic_id: str,
    workspace_id: str = Query(...),
    current_user=Depends(get_current_user_required),
    service: SearchTopicService = Depends(get_search_topic_service),
) -> dict[str, Any]:
    """Reset a built-in topic to its shipped definition, or delete a custom one."""
    await require_workspace_admin(current_user.id, workspace_id)
    try:
        restored = await service.reset_topic(workspace_id, topic_id)
    except Exception as exc:
        raise _http_error(exc) from exc
    return {"topic": restored.to_dict() if restored else None}
