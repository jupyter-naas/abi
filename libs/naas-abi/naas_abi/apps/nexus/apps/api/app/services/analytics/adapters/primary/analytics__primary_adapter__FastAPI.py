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
    ChatAgentRow,
    ChatAnalyticsKpi,
    ChatAnalyticsResponse,
    ChatDetail,
    ChatFeedbackRow,
    ChatMessage,
    ChatToolRow,
    ChatTopRow,
    ChatsResponse,
    EventsResponse,
    IngestResponse,
    Metadata,
    OverviewResponse,
    PagesResponse,
    RebuildResponse,
    ScenariosResponse,
    SessionsResponse,
    TimeseriesPoint,
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


@router.get("/chat-analytics", response_model=ChatAnalyticsResponse)
async def get_chat_analytics(
    scenario_id: str = Query(DEFAULT_SCENARIO_ID),
    workspace_id: str | None = Query(None),
    user_email: str | None = Query(None),
    service: AnalyticsService = Depends(get_analytics_service),
    registry=Depends(get_service_registry),
) -> ChatAnalyticsResponse:
    """Aggregate chat-level KPIs, timeseries and ranked tables for the analytics UI.

    Conversations are sourced directly from the chat DB (by updated_at within
    the scenario window) so they appear regardless of whether a page_viewed
    analytics event was recorded.
    """
    from collections import defaultdict
    from datetime import datetime

    # -- Resolve scenario window -----------------------------------------------
    scenario_days = service._days_for_scenario(scenario_id)
    zero_series = [TimeseriesPoint(date=d, value=0) for d in scenario_days]

    scenario = next(
        (s for s in service.get_scenarios().scenarios if s.scenario_id == scenario_id),
        None,
    )
    if scenario is None:
        return ChatAnalyticsResponse(
            kpi=ChatAnalyticsKpi(num_chats=0, num_messages=0),
            messages_over_time=zero_series,
            chats_over_time=zero_series,
            top_agents=[], top_tools=[], feedback_distribution=[], top_chats=[],
        )

    date_start = datetime.fromisoformat(scenario.date_start.replace("Z", "+00:00"))
    date_end = datetime.fromisoformat(scenario.date_end.replace("Z", "+00:00"))

    chat_service = registry.chat

    # -- Source conversations from the chat DB by updated_at -------------------
    conv_list = await chat_service.adapter.list_conversations_by_updated_at(
        date_start=date_start,
        date_end=date_end,
        workspace_id=workspace_id if workspace_id and workspace_id != "all" else None,
    )

    # Apply user_email filter by cross-referencing analytics ref-users.
    if user_email and user_email != "all":
        ref: list[dict] = service._storage.load_json("ref-users.json", fallback=[])
        uid = next(
            (u.get("user_id") for u in ref if u.get("user_email") == user_email),
            None,
        )
        conv_list = [c for c in conv_list if c.user_id == uid] if uid else []

    if not conv_list:
        return ChatAnalyticsResponse(
            kpi=ChatAnalyticsKpi(num_chats=0, num_messages=0),
            messages_over_time=zero_series,
            chats_over_time=zero_series,
            top_agents=[], top_tools=[], feedback_distribution=[], top_chats=[],
        )

    ids = [c.id for c in conv_list]
    conversations = {c.id: c for c in conv_list}

    # -- Resolve agent IDs → human-readable names (single round-trip) ---------
    agent_ids = {c.agent for c in conv_list if c.agent}
    agent_name_map: dict[str, str] = await chat_service.adapter.list_agent_names_by_ids(agent_ids)

    # -- Batch-fetch counts and messages (sequential — one session, no gather) -
    counts = await chat_service.adapter.count_messages_for_conversations(ids)
    messages_by_conv = await chat_service.adapter.list_messages_for_conversations(ids)

    # Hourly or daily buckets depending on the scenario.
    hourly = scenario_id in ("today", "yesterday")
    slot_fmt = "%Y-%m-%dT%H" if hourly else "%Y-%m-%d"

    # -- Aggregate over messages -----------------------------------------------
    likes = dislikes = 0
    tools_used: dict[str, int] = defaultdict(int)
    feedback_types: dict[str, int] = defaultdict(int)
    msgs_by_slot: dict[str, int] = defaultdict(int)

    for cid, msgs in messages_by_conv.items():
        for msg in msgs:
            meta = _parse_message_metadata(msg.metadata_)
            if meta:
                fb = meta.get("feedback")
                if fb == "like":
                    likes += 1
                elif fb == "dislike":
                    dislikes += 1
                    ft = meta.get("feedback_type")
                    if ft and isinstance(ft, str):
                        feedback_types[ft] += 1
                for step in meta.get("steps") or []:
                    tool = step.get("tool_name") if isinstance(step, dict) else None
                    if tool and isinstance(tool, str) and tool.lower() != "thinking":
                        tools_used[tool] += 1
            msgs_by_slot[msg.created_at.strftime(slot_fmt)] += 1

    # -- Per-agent aggregation -------------------------------------------------
    agent_msgs: dict[str, int] = defaultdict(int)
    agent_chats: dict[str, int] = defaultdict(int)
    for conv in conv_list:
        slug = conv.agent or "unknown"
        agent = agent_name_map.get(slug, slug)
        agent_chats[agent] += 1
        agent_msgs[agent] += counts.get(conv.id, 0)

    # -- KPI -------------------------------------------------------------------
    total_messages = sum(counts.values())
    most_agent = max(agent_chats, key=lambda a: agent_msgs[a]) if agent_chats else None
    most_tool = max(tools_used, key=tools_used.__getitem__) if tools_used else None

    kpi = ChatAnalyticsKpi(
        num_chats=len(conv_list),
        num_messages=total_messages,
        messages_liked=likes,
        messages_disliked=dislikes,
        agents_used=len(agent_chats),
        most_agent_used=most_agent,
        tools_used=len(tools_used),
        most_tool_used=most_tool,
    )

    # -- Time series -----------------------------------------------------------
    chats_by_slot: dict[str, int] = defaultdict(int)
    for conv in conv_list:
        chats_by_slot[conv.updated_at.strftime(slot_fmt)] += 1

    if scenario_days:
        chats_over_time = [TimeseriesPoint(date=d, value=chats_by_slot.get(d, 0)) for d in scenario_days]
        messages_over_time = [TimeseriesPoint(date=d, value=msgs_by_slot.get(d, 0)) for d in scenario_days]
    else:
        all_slots = sorted(set(list(chats_by_slot) + list(msgs_by_slot)))
        chats_over_time = [TimeseriesPoint(date=d, value=chats_by_slot.get(d, 0)) for d in all_slots]
        messages_over_time = [TimeseriesPoint(date=d, value=msgs_by_slot.get(d, 0)) for d in all_slots]

    # -- Ranked tables ---------------------------------------------------------
    top_agents = sorted(
        [ChatAgentRow(agent=a, messages=agent_msgs[a], chats=agent_chats[a]) for a in agent_chats],
        key=lambda r: r.messages, reverse=True,
    )
    top_tools = sorted(
        [ChatToolRow(tool_name=t, uses=u) for t, u in tools_used.items()],
        key=lambda r: r.uses, reverse=True,
    )
    feedback_distribution = sorted(
        [ChatFeedbackRow(feedback_type=ft, count=cnt) for ft, cnt in feedback_types.items()],
        key=lambda r: r.count, reverse=True,
    )

    top_chats: list[ChatTopRow] = []
    for conv in conv_list:
        msgs = messages_by_conv.get(conv.id, [])
        lk = dk = 0
        last_msg_at: str | None = None
        for msg in msgs:
            meta = _parse_message_metadata(msg.metadata_)
            if meta:
                fb = meta.get("feedback")
                if fb == "like":
                    lk += 1
                elif fb == "dislike":
                    dk += 1
            ts = msg.created_at.isoformat() + "Z"
            if last_msg_at is None or ts > last_msg_at:
                last_msg_at = ts
        top_chats.append(
            ChatTopRow(
                conversation_id=conv.id,
                title=conv.title or conv.id,
                user_email=None,  # user_id stored, not email — enriched below
                workspace_name=conv.workspace_id,
                message_count=counts.get(conv.id, 0),
                likes=lk,
                dislikes=dk,
                agent=agent_name_map.get(conv.agent or "", conv.agent or ""),
                last_message_at=last_msg_at,
            )
        )

    # Enrich user_email from analytics ref-users (best-effort).
    ref_users: list[dict] = service._storage.load_json("ref-users.json", fallback=[])
    uid_to_email = {u.get("user_id"): u.get("user_email") for u in ref_users if u.get("user_id")}
    for row in top_chats:
        conv = conversations.get(row.conversation_id)
        if conv:
            row.user_email = uid_to_email.get(conv.user_id)

    # Enrich workspace_name from analytics ref-workspaces (best-effort).
    ref_ws: list[dict] = service._storage.load_json("ref-workspaces.json", fallback=[])
    wsid_to_name = {w.get("workspace_id"): w.get("workspace_name") for w in ref_ws if w.get("workspace_id")}
    for row in top_chats:
        conv = conversations.get(row.conversation_id)
        if conv:
            row.workspace_name = wsid_to_name.get(conv.workspace_id, conv.workspace_id)

    top_chats.sort(key=lambda r: r.message_count, reverse=True)

    return ChatAnalyticsResponse(
        kpi=kpi,
        messages_over_time=messages_over_time,
        chats_over_time=chats_over_time,
        top_agents=top_agents,
        top_tools=top_tools,
        feedback_distribution=feedback_distribution,
        top_chats=top_chats,
    )


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
            created_at=m.created_at.isoformat() + "Z" if m.created_at else None,
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
        created_at=conversation.created_at.isoformat() + "Z" if conversation.created_at else None,
        updated_at=conversation.updated_at.isoformat() + "Z" if conversation.updated_at else None,
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
