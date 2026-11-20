"""Analytics of an organization and of a workspace (epic #1533).

``/api/organizations/{org_id}/analytics/...`` (``ReadOrganizationAnalytics``: the
organization's owners and admins) and ``/api/workspaces/{workspace_id}/analytics/...``
(``ReadWorkspaceAnalytics``: the workspace's admins and owners, and the
organization's through their org-wide role). The routes and their responses are
the contract shared with the web app (``docs/adr/20261119_analytics_scoped_rollups.md``).

The scope is resolved here, on the server, before the domain service runs:

* organization: its workspaces (``workspaces.organization_id``) and its people, as
  its directory lists them (who holds a role at the organization's container, below
  it, or in one of its workspaces, from IAM);
* workspace: that workspace, and who holds a role there or reaches it through an
  org-wide role (as the workspace's member list shows them).

A ``workspace_id``, ``user_id`` or ``conversation_id`` the scope does not hold is
not found (404). A conversation's messages and its export also need
``ReadAnalyticsConversation`` in the conversation's workspace, which no role holds.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__postgres import (  # noqa: E501
    AnalyticsSecondaryAdapterPostgresQueries,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.periods import DEFAULT_TIMEZONE
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsAccess,
    AnalyticsQueryPort,
    AnalyticsScope,
    ChatAnalyticsResponse,
    ChatDetail,
    ChatMessage,
    ChatsResponse,
    EventsResponse,
    OutOfScope,
    OverviewResponse,
    PagesResponse,
    SessionsResponse,
    UserDetail,
    UsersResponse,
    WorkspacesResponse,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.scoped_service import (
    ScopedAnalyticsService,
    iso,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__export import (  # noqa: E501
    export_conversation_as_response,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import authz as authz_module
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_below,
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.registry import get_service_registry
from naas_abi.apps.nexus.apps.api.app.services.view_as.confinement import (
    outside_this_organization,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

PeriodParam = Literal["today", "yesterday", "this_week", "this_month"]
READ_CONVERSATION = "ReadAnalyticsConversation"
# The id a scope-wide check of ``ReadAnalyticsConversation`` is asked on: a policy
# granting it names ``analytics_conversation/*`` (or one conversation, then the
# figures still say no and the conversation's own check decides).
ANY_CONVERSATION = "*"

organization_router = APIRouter(dependencies=[Depends(get_current_user_required)])
workspace_router = APIRouter(dependencies=[Depends(get_current_user_required)])

_ORG_GUARD = [guard("ReadOrganizationAnalytics", workspace=None, org="org_id")]
_WORKSPACE_GUARD = [guard("ReadWorkspaceAnalytics")]


def get_analytics_queries(db: AsyncSession = Depends(get_db)) -> AnalyticsQueryPort:
    return AnalyticsSecondaryAdapterPostgresQueries(db)


def scoped_analytics_over(
    db: AsyncSession, *, now: Callable[[], datetime] | None = None
) -> ScopedAnalyticsService:
    """The service over the session ``db``; on PostgreSQL, a page's several reads (the
    overview's five) also run at the same time, each on a session of its own from the
    same engine (one connection runs one statement at a time). SQLite (tests, a single
    file or memory connection) reads one after another."""
    queries = AnalyticsSecondaryAdapterPostgresQueries(db)
    bind = db.bind
    # An engine hands out connections; a session bound to one connection (a test's
    # transaction) cannot share it between statements running at once.
    if not isinstance(bind, AsyncEngine) or bind.dialect.name != "postgresql":
        return ScopedAnalyticsService(queries, now=now)
    sessions = async_sessionmaker(bind, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def apart() -> AsyncIterator[AnalyticsQueryPort]:
        async with sessions() as session:
            yield AnalyticsSecondaryAdapterPostgresQueries(session)

    return ScopedAnalyticsService(queries, now=now, parallel=apart)


def get_scoped_analytics(db: AsyncSession = Depends(get_db)) -> ScopedAnalyticsService:
    return scoped_analytics_over(db)


# ---------------------------------------------------------------------------
# Scope resolution
# ---------------------------------------------------------------------------


# Who holds a role where, read from IAM in one pass over the roles' attachments: a
# settings page asks for several figures at once, so a scope's members are kept
# this long (a change of roles shows in the figures after at most that).
# A cold cache asked by the page's parallel requests at once runs one IAM pass:
# the others await the one in flight (``_members_loading``).
_MEMBERS_SECONDS = 15.0
_members_cache: dict[tuple[str, ...], tuple[dict[str, set[str]], float]] = {}
_members_loading: dict[tuple[str, ...], asyncio.Future[dict[str, set[str]]]] = {}


async def _load_members(key: tuple[str, ...]) -> dict[str, set[str]]:
    found = await MEMBERSHIPS.members_of(list(key))
    members = {scope: {m.user_id for m in found.get(scope, [])} for scope in key}
    if len(_members_cache) > 1000:
        _members_cache.clear()
    _members_cache[key] = (members, time.monotonic() + _MEMBERS_SECONDS)
    return members


async def _members_of(scopes: list[str]) -> dict[str, set[str]]:
    key = tuple(sorted(set(scopes)))
    cached = _members_cache.get(key)
    if cached is not None and cached[1] > time.monotonic():
        return cached[0]
    loading = _members_loading.get(key)
    if loading is None:
        loading = asyncio.ensure_future(_load_members(key))
        _members_loading[key] = loading
        loading.add_done_callback(lambda _done, k=key: _members_loading.pop(k, None))
    # Shielded: one waiter cancelled (its client gone) leaves the pass to the others.
    return await asyncio.shield(loading)


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} not found")


async def organization_scope(
    org_id: str = Path(...),
    queries: AnalyticsQueryPort = Depends(get_analytics_queries),
) -> AnalyticsScope:
    if (outside := outside_this_organization(org_id)) is not None:
        raise HTTPException(status_code=403, detail=outside)
    timezone = await queries.organization_timezone(org_id)
    if timezone is None:
        raise _not_found("Organization")
    workspace_ids = await queries.organization_workspaces(org_id)
    containers = {ws: workspace_container(org_id, ws) for ws in workspace_ids}
    found = await _members_of([org_container(org_id), org_below(org_id), *containers.values()])
    org_wide = found[org_below(org_id)]
    held: dict[str, list[str]] = {}
    for ws, container in containers.items():
        for uid in found[container]:
            held.setdefault(uid, []).append(ws)
    # The organization's directory (``MEMBERSHIPS.org_directory``, epic #1566): who holds
    # a role at the organization, below it, or only in one of its workspaces. Someone
    # added to a workspace gets no organization role, and still counts here.
    members = sorted(found[org_container(org_id)] | org_wide | held.keys())
    return AnalyticsScope(
        kind="organization",
        organization_id=org_id,
        workspace_ids=tuple(workspace_ids),
        member_ids=tuple(members),
        timezone=timezone or DEFAULT_TIMEZONE,
        member_workspaces={
            uid: tuple(workspace_ids) if uid in org_wide else tuple(held.get(uid, ()))
            for uid in members
        },
    )


async def workspace_scope(
    workspace_id: str = Path(...),
    queries: AnalyticsQueryPort = Depends(get_analytics_queries),
) -> AnalyticsScope:
    exists, org_id = await queries.workspace_organization(workspace_id)
    if not exists:
        raise _not_found("Workspace")
    timezone = (await queries.organization_timezone(org_id) if org_id else None) or (
        DEFAULT_TIMEZONE
    )
    container = await authz_module.AUTHZ.container_of(workspace_id) or workspace_container(
        org_id, workspace_id
    )
    scopes = [container] + ([org_below(org_id)] if org_id else [])
    found = await _members_of(scopes)
    members = sorted({uid for scope in scopes for uid in found[scope]})
    return AnalyticsScope(
        kind="workspace",
        organization_id=org_id,
        workspace_ids=(workspace_id,),
        member_ids=tuple(members),
        timezone=timezone,
        member_workspaces=dict.fromkeys(members, (workspace_id,)),
    )


def _narrow(
    scope: AnalyticsScope, *, workspace_id: str | None = None, user_id: str | None = None
) -> AnalyticsScope:
    # ``all`` is what the analytics app sends for "no filter".
    workspace_id = None if workspace_id in (None, "", "all") else workspace_id
    user_id = None if user_id in (None, "", "all") else user_id
    try:
        return scope.narrowed(workspace_id=workspace_id, user_id=user_id)
    except OutOfScope as exc:
        raise _not_found(exc.what) from exc


async def organization_scope_filtered(
    scope: AnalyticsScope = Depends(organization_scope),
    workspace_id: str | None = Query(None),
    user_id: str | None = Query(None),
) -> AnalyticsScope:
    return _narrow(scope, workspace_id=workspace_id, user_id=user_id)


async def organization_scope_by_workspace(
    scope: AnalyticsScope = Depends(organization_scope),
    workspace_id: str | None = Query(None),
) -> AnalyticsScope:
    return _narrow(scope, workspace_id=workspace_id)


async def workspace_scope_filtered(
    scope: AnalyticsScope = Depends(workspace_scope),
    user_id: str | None = Query(None),
) -> AnalyticsScope:
    return _narrow(scope, user_id=user_id)


async def _can_read_conversations(user: Any, scope: AnalyticsScope) -> bool:
    if not scope.workspace_ids:
        return False
    return await authz_module.AUTHZ.allowed_in_any(
        READ_CONVERSATION,
        user=user,
        workspaces=[(scope.organization_id, ws) for ws in scope.workspace_ids],
        id=ANY_CONVERSATION,
    )


# ---------------------------------------------------------------------------
# Conversations behind the figures
# ---------------------------------------------------------------------------


def _metadata(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


async def _readable_conversation(
    scope: AnalyticsScope, conversation_id: str, user: Any, queries: AnalyticsQueryPort
):
    conversation = await queries.conversation_in_scope(scope, conversation_id)
    if conversation is None:
        raise _not_found("Conversation")
    await authz_module.AUTHZ.require(
        READ_CONVERSATION,
        user=user,
        workspace=conversation.workspace_id,
        id=conversation_id,
        denied="Reading a conversation's messages needs ReadAnalyticsConversation",
    )
    return conversation


async def _chat_detail(
    scope: AnalyticsScope,
    conversation_id: str,
    user: Any,
    queries: AnalyticsQueryPort,
    registry: Any,
) -> ChatDetail:
    conversation = await _readable_conversation(scope, conversation_id, user, queries)
    records = await registry.chat.adapter.list_messages_by_conversation(conversation_id)
    return ChatDetail(
        conversation_id=conversation.conversation_id,
        workspace_id=conversation.workspace_id,
        user_id=conversation.user_id,
        title=conversation.title,
        agent=conversation.agent,
        created_at=iso(conversation.created_at) or None,
        updated_at=iso(conversation.updated_at) or None,
        messages=[
            ChatMessage(
                id=m.id,
                role=m.role,
                content=m.content,
                agent=m.agent,
                created_at=iso(m.created_at) or None,
                metadata=_metadata(m.metadata_),
            )
            for m in records
        ],
    )


async def _chat_export(
    scope: AnalyticsScope,
    conversation_id: str,
    export_format: str,
    user: Any,
    queries: AnalyticsQueryPort,
    registry: Any,
):
    await _readable_conversation(scope, conversation_id, user, queries)
    adapter = registry.chat.adapter
    conversation = await adapter.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise _not_found("Conversation")
    messages = await adapter.list_messages_by_conversation(conversation_id)
    return export_conversation_as_response(
        conversation_id=conversation_id,
        format=export_format,
        user_id=conversation.user_id,
        conversation=conversation,
        messages=messages,
        messages_metadata=None,
    )


# ---------------------------------------------------------------------------
# Routes, the same under both scopes
# ---------------------------------------------------------------------------

ScopeDependency = Callable[..., Awaitable[AnalyticsScope]]


def _register(
    router: APIRouter,
    *,
    base: str,
    guards: list,
    scope_of: ScopeDependency,
    filtered: ScopeDependency,
    by_workspace: ScopeDependency,
    with_workspaces: bool,
) -> None:
    @router.get(f"{base}/overview", response_model=OverviewResponse, dependencies=guards)
    async def overview(
        period: PeriodParam = Query("today"),
        scope: AnalyticsScope = Depends(filtered),
        service: ScopedAnalyticsService = Depends(get_scoped_analytics),
    ) -> OverviewResponse:
        return await service.overview(scope, service.window(scope, period))

    @router.get(f"{base}/users", response_model=UsersResponse, dependencies=guards)
    async def users(
        period: PeriodParam = Query("today"),
        scope: AnalyticsScope = Depends(filtered),
        service: ScopedAnalyticsService = Depends(get_scoped_analytics),
    ) -> UsersResponse:
        return await service.users(scope, service.window(scope, period))

    @router.get(f"{base}/users/{{user_id}}", response_model=UserDetail, dependencies=guards)
    async def user_detail(
        user_id: str,
        period: PeriodParam = Query("today"),
        scope: AnalyticsScope = Depends(by_workspace),
        service: ScopedAnalyticsService = Depends(get_scoped_analytics),
    ) -> UserDetail:
        narrowed = _narrow(scope, user_id=user_id)
        return await service.user_detail(narrowed, service.window(narrowed, period))

    @router.get(f"{base}/sessions", response_model=SessionsResponse, dependencies=guards)
    async def sessions(
        period: PeriodParam = Query("today"),
        scope: AnalyticsScope = Depends(filtered),
        service: ScopedAnalyticsService = Depends(get_scoped_analytics),
    ) -> SessionsResponse:
        return await service.sessions(scope, service.window(scope, period))

    @router.get(f"{base}/pages", response_model=PagesResponse, dependencies=guards)
    async def pages(
        period: PeriodParam = Query("today"),
        scope: AnalyticsScope = Depends(filtered),
        service: ScopedAnalyticsService = Depends(get_scoped_analytics),
    ) -> PagesResponse:
        return await service.pages(scope, service.window(scope, period))

    if with_workspaces:

        @router.get(f"{base}/workspaces", response_model=WorkspacesResponse, dependencies=guards)
        async def workspaces(
            period: PeriodParam = Query("today"),
            whole: AnalyticsScope = Depends(scope_of),
            scope: AnalyticsScope = Depends(filtered),
            service: ScopedAnalyticsService = Depends(get_scoped_analytics),
        ) -> WorkspacesResponse:
            return await service.workspaces(
                scope, service.window(scope, period), directory=whole.workspace_ids
            )

    @router.get(f"{base}/events", response_model=EventsResponse, dependencies=guards)
    async def events(
        period: PeriodParam = Query("today"),
        limit: int = Query(200, ge=1, le=500),
        scope: AnalyticsScope = Depends(filtered),
        service: ScopedAnalyticsService = Depends(get_scoped_analytics),
    ) -> EventsResponse:
        return await service.events(scope, service.window(scope, period), limit=limit)

    @router.get(f"{base}/chats", response_model=ChatsResponse, dependencies=guards)
    async def chats(
        period: PeriodParam = Query("today"),
        scope: AnalyticsScope = Depends(filtered),
        user=Depends(get_current_user_required),
        service: ScopedAnalyticsService = Depends(get_scoped_analytics),
    ) -> ChatsResponse:
        return await service.chats(
            scope,
            service.window(scope, period),
            can_read_messages=await _can_read_conversations(user, scope),
        )

    @router.get(f"{base}/chat-analytics", response_model=ChatAnalyticsResponse, dependencies=guards)
    async def chat_analytics(
        period: PeriodParam = Query("today"),
        scope: AnalyticsScope = Depends(filtered),
        service: ScopedAnalyticsService = Depends(get_scoped_analytics),
    ) -> ChatAnalyticsResponse:
        return await service.chat_analytics(scope, service.window(scope, period))

    @router.get(
        f"{base}/chats/{{conversation_id}}",
        response_model=ChatDetail,
        dependencies=[*guards, declares(READ_CONVERSATION)],
    )
    async def chat_detail(
        conversation_id: str,
        scope: AnalyticsScope = Depends(by_workspace),
        user=Depends(get_current_user_required),
        queries: AnalyticsQueryPort = Depends(get_analytics_queries),
        registry=Depends(get_service_registry),
    ) -> ChatDetail:
        return await _chat_detail(scope, conversation_id, user, queries, registry)

    @router.get(
        f"{base}/chats/{{conversation_id}}/export",
        dependencies=[*guards, declares(READ_CONVERSATION)],
    )
    async def chat_export(
        conversation_id: str,
        format: str = Query("txt", pattern="^(txt|json|md)$"),
        scope: AnalyticsScope = Depends(by_workspace),
        user=Depends(get_current_user_required),
        queries: AnalyticsQueryPort = Depends(get_analytics_queries),
        registry=Depends(get_service_registry),
    ):
        return await _chat_export(scope, conversation_id, format, user, queries, registry)


_register(
    organization_router,
    base="/{org_id}/analytics",
    guards=_ORG_GUARD,
    scope_of=organization_scope,
    filtered=organization_scope_filtered,
    by_workspace=organization_scope_by_workspace,
    with_workspaces=True,
)
_register(
    workspace_router,
    base="/{workspace_id}/analytics",
    guards=_WORKSPACE_GUARD,
    scope_of=workspace_scope,
    filtered=workspace_scope_filtered,
    by_workspace=workspace_scope,
    with_workspaces=False,
)


def _no_access() -> AnalyticsAccess:
    return AnalyticsAccess(can_read=False, can_read_conversations=False, timezone=DEFAULT_TIMEZONE)


# What the caller may read: never 403 to a signed-in user (the settings nav asks it).
# The action is decided inline, hence ``declares``.
@organization_router.get(
    "/{org_id}/analytics/access",
    response_model=AnalyticsAccess,
    dependencies=[declares("ReadOrganizationAnalytics")],
)
async def organization_access(
    org_id: str,
    user=Depends(get_current_user_required),
    queries: AnalyticsQueryPort = Depends(get_analytics_queries),
) -> AnalyticsAccess:
    if outside_this_organization(org_id) is not None or not await authz_module.AUTHZ.allowed(
        "ReadOrganizationAnalytics", user=user, org=org_id
    ):
        return _no_access()
    try:
        scope = await organization_scope(org_id, queries)
    except HTTPException:
        return _no_access()
    return AnalyticsAccess(
        can_read=True,
        can_read_conversations=await _can_read_conversations(user, scope),
        timezone=scope.timezone,
    )


@workspace_router.get(
    "/{workspace_id}/analytics/access",
    response_model=AnalyticsAccess,
    dependencies=[declares("ReadWorkspaceAnalytics")],
)
async def workspace_access(
    workspace_id: str,
    user=Depends(get_current_user_required),
    queries: AnalyticsQueryPort = Depends(get_analytics_queries),
) -> AnalyticsAccess:
    if not await authz_module.AUTHZ.allowed(
        "ReadWorkspaceAnalytics", user=user, workspace=workspace_id
    ):
        return _no_access()
    try:
        scope = await workspace_scope(workspace_id, queries)
    except HTTPException:
        return _no_access()
    return AnalyticsAccess(
        can_read=True,
        can_read_conversations=await _can_read_conversations(user, scope),
        timezone=scope.timezone,
    )
