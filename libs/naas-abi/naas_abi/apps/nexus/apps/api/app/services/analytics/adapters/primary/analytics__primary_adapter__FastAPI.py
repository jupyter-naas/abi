"""FastAPI primary adapter for the analytics service.

Routes are intentionally thin: each one resolves a per-request
``AnalyticsService`` (storage-backed) and delegates to a single service
method. Read endpoints take a ``scenario_id`` query param and return the
matching slice of the prebuilt JSON — no aggregation or filtering happens
here.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary import (
    AnalyticsSecondaryAdapterObjectStorage,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsEvent,
    ChatDetail,
    ChatMessage,
    ChatsResponse,
    EventsResponse,
    IngestResponse,
    Metadata,
    OverviewResponse,
    PagesResponse,
    RebuildResponse,
    ScenariosResponse,
    SessionsResponse,
    UserDetail,
    UserDetailNotFound,
    UsersResponse,
    WorkspacesResponse,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.service import (
    DEFAULT_SCENARIO_ID,
    AnalyticsService,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__export import (
    export_conversation_as_response,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.service import ChatService
from naas_abi.apps.nexus.apps.api.app.services.registry import get_service_registry
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_message_metadata(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.debug("Unparseable message metadata; skipping")
        return None
    return data if isinstance(data, dict) else None


def _get_object_storage(request: Request) -> ObjectStorageService:
    storage = getattr(request.app.state, "object_storage", None)
    if storage is not None:
        return storage
    try:
        from naas_abi import ABIModule

        module = ABIModule.get_instance()
        storage = module.engine.services.object_storage
        request.app.state.object_storage = storage
        return storage
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Object storage is not initialized. Load API through naas_abi.ABIModule.",
        ) from exc


def get_analytics_service(
    storage: ObjectStorageService = Depends(_get_object_storage),
) -> AnalyticsService:
    return AnalyticsService(
        storage=AnalyticsSecondaryAdapterObjectStorage(object_storage=storage)
    )


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


@router.post("/events", response_model=IngestResponse)
async def ingest_event(
    event: AnalyticsEvent,
    service: AnalyticsService = Depends(get_analytics_service),
) -> IngestResponse:
    stored_at = service.ingest_event(event)
    return IngestResponse(stored_at=stored_at)


@router.post("/rebuild", response_model=RebuildResponse)
async def rebuild_now(
    service: AnalyticsService = Depends(get_analytics_service),
) -> RebuildResponse:
    metadata = service.rebuild()
    return RebuildResponse(metadata=metadata)


@router.get("/metadata", response_model=Metadata | None)
async def get_metadata(
    service: AnalyticsService = Depends(get_analytics_service),
) -> Metadata | None:
    return service.get_metadata()


@router.get("/scenarios", response_model=ScenariosResponse)
async def get_scenarios(
    service: AnalyticsService = Depends(get_analytics_service),
) -> ScenariosResponse:
    return service.get_scenarios()


# ---------------------------------------------------------------------------
# Read path — each endpoint reads one slice of the matching prebuilt JSON
# ---------------------------------------------------------------------------


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    user_email: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> OverviewResponse:
    return service.get_overview(
        scenario_id=scenario_id, workspace_id=workspace_id, user_email=user_email
    )


@router.get("/users", response_model=UsersResponse)
async def get_users(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> UsersResponse:
    return service.get_users(scenario_id=scenario_id, workspace_id=workspace_id)


@router.get("/users/{email:path}", response_model=UserDetail)
async def get_user_detail(
    email: str,
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> UserDetail:
    try:
        return service.get_user_detail(
            email, scenario_id=scenario_id, workspace_id=workspace_id
        )
    except UserDetailNotFound as exc:
        raise HTTPException(
            status_code=404, detail="No data for user in selected range"
        ) from exc


@router.get("/sessions", response_model=SessionsResponse)
async def get_sessions(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    user_email: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> SessionsResponse:
    return service.get_sessions(
        scenario_id=scenario_id, workspace_id=workspace_id, user_email=user_email
    )


@router.get("/pages", response_model=PagesResponse)
async def get_pages(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    user_email: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> PagesResponse:
    return service.get_pages(
        scenario_id=scenario_id, workspace_id=workspace_id, user_email=user_email
    )


@router.get("/workspaces", response_model=WorkspacesResponse)
async def get_workspaces(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    user_email: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> WorkspacesResponse:
    return service.get_workspaces(
        scenario_id=scenario_id, workspace_id=workspace_id, user_email=user_email
    )


@router.get("/events", response_model=EventsResponse)
async def get_events(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    limit: int = Query(200, ge=1, le=1000),
    workspace_id: str | None = Query(None),
    user_email: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
) -> EventsResponse:
    return service.get_events(
        scenario_id=scenario_id,
        limit=limit,
        workspace_id=workspace_id,
        user_email=user_email,
    )


@router.get("/chats", response_model=ChatsResponse)
async def get_chats(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    user_email: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
    registry=Depends(get_service_registry),
) -> ChatsResponse:
    response = service.get_chats(
        scenario_id=scenario_id, workspace_id=workspace_id, user_email=user_email
    )
    if response.chats:
        chat_service: ChatService = registry.chat
        ids = [c.conversation_id for c in response.chats]
        counts = await chat_service.adapter.count_messages_for_conversations(ids)
        chats_by_id = await chat_service.adapter.list_conversations_by_ids(ids)
        for row in response.chats:
            row.message_count = counts.get(row.conversation_id, 0)
            chat = chats_by_id.get(row.conversation_id)
            if chat is not None:
                row.chat_title = chat.title
    return response


@router.get("/chats/{conversation_id}", response_model=ChatDetail)
async def get_chat_detail(
    conversation_id: str,
    registry=Depends(get_service_registry),
) -> ChatDetail:
    chat_service: ChatService = registry.chat
    conversation = await chat_service.adapter.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    records = await chat_service.adapter.list_messages_by_conversation(conversation_id)

    messages = [
        ChatMessage(
            id=m.id,
            role=m.role,
            content=m.content,
            agent=m.agent,
            created_at=m.created_at.isoformat() if m.created_at else None,
            metadata=_parse_message_metadata(m.metadata_),
        )
        for m in records
    ]

    return ChatDetail(
        conversation_id=conversation.id,
        workspace_id=conversation.workspace_id,
        user_id=conversation.user_id,
        title=conversation.title,
        agent=conversation.agent,
        created_at=conversation.created_at.isoformat() if conversation.created_at else None,
        updated_at=conversation.updated_at.isoformat() if conversation.updated_at else None,
        messages=messages,
    )


class ChatFeedbackUpdate(BaseModel):
    """Body for ``PATCH /chats/{cid}/messages/{mid}/feedback``.

    ``feedback=None`` clears any previously set value, so the UI can toggle a
    thumbs-up off by sending ``{"feedback": null}``. The optional details
    fields (``feedback_type``, ``feedback_detail``, ``feedback_severity``)
    are only persisted alongside a ``dislike`` and are cleared on like / null.
    """

    feedback: Literal["like", "dislike"] | None = None
    feedback_type: str | None = None
    feedback_detail: str | None = None
    feedback_severity: int | None = None


_FEEDBACK_DETAIL_KEYS = ("feedback_type", "feedback_detail", "feedback_severity")


@router.patch("/chats/{conversation_id}/messages/{message_id}/feedback")
async def update_chat_message_feedback(
    conversation_id: str,
    message_id: str,
    payload: ChatFeedbackUpdate,
    registry=Depends(get_service_registry),
):
    """Admin-side feedback toggle for an assistant message.

    Reads the message's current metadata, merges (or removes) the ``feedback``
    key, and writes it back. Used by the analytics chat detail view so
    reviewers can flag bad / good AI responses; the value is also picked up
    by the export helper and the analytics list.
    """
    chat_service: ChatService = registry.chat
    messages = await chat_service.adapter.list_messages_by_conversation(conversation_id)
    target = next((m for m in messages if m.id == message_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Message not found")

    existing = _parse_message_metadata(target.metadata_) or {}
    if payload.feedback is None:
        existing.pop("feedback", None)
        for key in _FEEDBACK_DETAIL_KEYS:
            existing.pop(key, None)
    else:
        existing["feedback"] = payload.feedback
        if payload.feedback == "dislike":
            if payload.feedback_type:
                existing["feedback_type"] = payload.feedback_type
            else:
                existing.pop("feedback_type", None)
            if payload.feedback_detail:
                existing["feedback_detail"] = payload.feedback_detail
            else:
                existing.pop("feedback_detail", None)
            if payload.feedback_severity is not None:
                existing["feedback_severity"] = payload.feedback_severity
            else:
                existing.pop("feedback_severity", None)
        else:
            for key in _FEEDBACK_DETAIL_KEYS:
                existing.pop(key, None)

    updated = await chat_service.adapter.update_message_metadata(
        message_id=message_id,
        metadata=json.dumps(existing),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Message not found")
    return {
        "status": "updated",
        "feedback": payload.feedback,
        "feedback_type": existing.get("feedback_type"),
        "feedback_detail": existing.get("feedback_detail"),
        "feedback_severity": existing.get("feedback_severity"),
    }


@router.get("/chats/{conversation_id}/export")
async def export_chat(
    conversation_id: str,
    format: str = Query("txt", pattern="^(txt|json|md)$"),
    registry=Depends(get_service_registry),
):
    """Admin export of a conversation for the analytics UI.

    Delegates to the same ``export_conversation_as_response`` helper the chat
    interface uses, so the analytics download and the in-chat download produce
    byte-identical files.
    """
    chat_service: ChatService = registry.chat
    conversation = await chat_service.adapter.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await chat_service.adapter.list_messages_by_conversation(conversation_id)
    return export_conversation_as_response(
        conversation_id=conversation_id,
        format=format,
        user_id=conversation.user_id,
        conversation=conversation,
        messages=messages,
        messages_metadata=None,
    )
