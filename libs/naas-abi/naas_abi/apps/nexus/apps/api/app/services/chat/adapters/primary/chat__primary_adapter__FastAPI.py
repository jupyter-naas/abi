"""Chat FastAPI primary adapter."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.chat import ChatService
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__dependencies import (
    bind_registry,
    get_chat_service,
    request_context,
    to_complete_chat_input,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__export import (
    export_conversation_as_response,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (
    ChatRequest,
    ChatResponse,
    Conversation,
    ConversationCreate,
    Message,
    to_conversation,
    to_message,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__streaming import (
    stream_chat_response,
)
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import check_ollama_status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


@router.get("/conversations")
async def list_conversations(
    workspace_id: str,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    current_user: User = Depends(get_current_user_required),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[Conversation]:
    await require_workspace_access(current_user.id, workspace_id)
    records = await chat_service.list_conversations(
        context=request_context(current_user),
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )
    return [to_conversation(r) for r in records]


@router.post("/conversations")
async def create_conversation(
    conv: ConversationCreate,
    current_user: User = Depends(get_current_user_required),
    chat_service: ChatService = Depends(get_chat_service),
) -> Conversation:
    await require_workspace_access(current_user.id, conv.workspace_id)
    row = await chat_service.create_conversation(
        context=request_context(current_user),
        workspace_id=conv.workspace_id,
        title=conv.title,
        agent=conv.agent,
        now=datetime.now(UTC).replace(tzinfo=None),
    )
    return to_conversation(row)


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    include_messages: bool = True,
    current_user: User = Depends(get_current_user_required),
    chat_service: ChatService = Depends(get_chat_service),
) -> Conversation:
    row = await chat_service.get_conversation_for_user(
        context=request_context(current_user),
        conversation_id=conversation_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await require_workspace_access(current_user.id, row.workspace_id)

    messages = []
    if include_messages:
        messages = [
            to_message(m)
            for m in await chat_service.list_messages(
                context=request_context(current_user),
                conversation_id=conversation_id,
            )
        ]

    return to_conversation(row, messages)


@router.post("/complete")
async def complete_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    with bind_registry(db) as registry:
        try:
            result = await registry.chat.complete_chat_request(
                context=request_context(current_user),
                request=to_complete_chat_input(request=request),
                now=datetime.now(UTC).replace(tzinfo=None),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ChatResponse(
        conversation_id=result.conversation_id,
        message=Message(
            id=result.assistant_message_id,
            conversation_id=result.conversation_id,
            role="assistant",
            content=result.assistant_content,
            agent=result.assistant_agent,
            created_at=datetime.now(UTC),
        ),
        context_used=[],
        provider_used=result.provider_used,
    )


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user_required),
):
    return await stream_chat_response(request=request, current_user=current_user)


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: str,
    updates: dict,
    current_user: User = Depends(get_current_user_required),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, str]:
    row = await chat_service.get_conversation_for_user(
        context=request_context(current_user),
        conversation_id=conversation_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await require_workspace_access(current_user.id, row.workspace_id)

    await chat_service.update_conversation(
        context=request_context(current_user),
        conversation_id=conversation_id,
        now=datetime.now(UTC),
        title=updates.get("title"),
        pinned=updates.get("pinned"),
        archived=updates.get("archived"),
    )
    return {"status": "updated"}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user_required),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, str]:
    row = await chat_service.get_conversation_for_user(
        context=request_context(current_user),
        conversation_id=conversation_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await require_workspace_access(current_user.id, row.workspace_id)
    await chat_service.delete_conversation_with_messages(
        context=request_context(current_user),
        conversation_id=conversation_id,
    )
    return {"status": "deleted"}


@router.get("/conversations/{conversation_id}/export")
async def export_conversation(
    conversation_id: str,
    format: str = Query(default="txt", pattern="^(txt|json|md)$"),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    with bind_registry(db) as registry:
        conv = await registry.chat.get_conversation_for_user(
            context=request_context(current_user),
            conversation_id=conversation_id,
        )
        messages = await registry.chat.list_messages(
            context=request_context(current_user),
            conversation_id=conversation_id,
        )

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await require_workspace_access(current_user.id, conv.workspace_id)
    logger.info(
        "📥 EXPORT: user=%s, conversation=%s, format=%s, messages=%s, workspace=%s",
        current_user.id,
        conversation_id,
        format,
        len(messages),
        conv.workspace_id,
    )

    return export_conversation_as_response(
        conversation_id=conversation_id,
        format=format,
        user_id=current_user.id,
        conversation=conv,
        messages=messages,
    )


@router.get("/ollama/status")
async def get_ollama_status(
    endpoint: str = "http://localhost:11434",
    current_user: User = Depends(get_current_user_required),
) -> dict:
    return await check_ollama_status(endpoint)
