from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

from fastapi import Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User
from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.core.postgres_session_registry import PostgresSessionRegistry
from naas_abi.apps.nexus.apps.api.app.services.chat import ChatService
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (
    ChatRequest,
    ProviderConfigRequest,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.chat__schema import (
    ChatInputMessage,
    ChatProviderConfigInput,
    CompleteChatInput,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import Message as ProviderMessage
from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry, get_service_registry
from sqlalchemy.ext.asyncio import AsyncSession


def request_context(current_user: User) -> RequestContext:
    session_id = PostgresSessionRegistry.instance().current_session_id()
    return RequestContext(
        token_data=TokenData(user_id=current_user.id, scopes={"*"}, is_authenticated=True),
        session_id=session_id,
    )


def system_request_context(user_id: str) -> RequestContext:
    session_id = PostgresSessionRegistry.instance().current_session_id()
    return RequestContext(
        token_data=TokenData(user_id=user_id, scopes={"*"}, is_authenticated=True),
        session_id=session_id,
    )


@contextmanager
def bind_registry(db: AsyncSession):
    session_registry = PostgresSessionRegistry.instance()
    session_id = f"sess-{uuid4().hex}"
    session_registry.bind(session_id=session_id, db=db)
    session_token = session_registry.set_current_session(session_id)
    registry = ServiceRegistry.instance()
    try:
        yield registry
    finally:
        session_registry.reset_current_session(session_token)
        session_registry.unbind(session_id)


def get_chat_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> ChatService:
    return registry.chat


def to_complete_chat_input(request: ChatRequest) -> CompleteChatInput:
    provider = None
    if request.provider:
        provider = ChatProviderConfigInput(
            id=request.provider.id,
            name=request.provider.name,
            type=request.provider.type,
            enabled=request.provider.enabled,
            endpoint=request.provider.endpoint,
            api_key=request.provider.api_key,
            account_id=request.provider.account_id,
            model=request.provider.model,
        )

    return CompleteChatInput(
        message=request.message,
        agent=request.agent,
        workspace_id=request.workspace_id,
        conversation_id=request.conversation_id,
        messages=[
            ChatInputMessage(
                role=m.role,
                content=m.content,
                images=m.images,
                agent=m.agent,
            )
            for m in request.messages
        ],
        images=request.images,
        provider=provider,
        system_prompt=request.system_prompt,
        context=request.context,
        search_enabled=request.search_enabled,
    )


async def resolve_provider(
    provider: ProviderConfigRequest | None,
    has_images: bool,
    agent_id: str | None = None,
    workspace_id: str | None = None,
) -> ProviderConfigRequest | None:
    async with AsyncSessionLocal() as db:
        with bind_registry(db) as registry:
            resolved = await registry.chat.resolve_provider(
                provider=provider,
                has_images=has_images,
                agent_id=agent_id,
                workspace_id=workspace_id,
            )
        if not resolved:
            return None
        return ProviderConfigRequest(
            id=resolved.id,
            name=resolved.name,
            type=resolved.type,
            enabled=resolved.enabled,
            endpoint=resolved.endpoint,
            api_key=resolved.api_key,
            account_id=resolved.account_id,
            model=resolved.model,
        )


async def get_or_create_conversation(
    chat_service: ChatService,
    request: ChatRequest,
    current_user: User,
    now: datetime,
) -> str:
    try:
        return await chat_service.get_or_create_conversation(
            conversation_id=request.conversation_id,
            workspace_id=request.workspace_id,
            context=request_context(current_user),
            request_message=request.message,
            agent=request.agent,
            now=now,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


async def build_provider_messages_with_agents(
    request: ChatRequest,
    context: RequestContext,
    current_agent_id: str,
    db: AsyncSession,
    conversation_id: str | None = None,
) -> list[ProviderMessage]:
    with bind_registry(db) as registry:
        return await registry.chat.build_provider_messages_with_agents(
            context=context,
            request=to_complete_chat_input(request=request),
            current_agent_id=current_agent_id,
            conversation_id=conversation_id,
        )


async def run_search_if_needed(request: ChatRequest) -> str | None:
    async with AsyncSessionLocal() as db:
        with bind_registry(db) as registry:
            return await registry.chat.run_search_if_needed(
                message=request.message,
                search_enabled=request.search_enabled,
            )


async def persist_stream_content(
    user_id: str,
    conversation_id: str,
    assistant_msg_id: str,
    full_response: str,
    touch_conversation: bool = False,
) -> None:
    async with AsyncSessionLocal() as db:
        with bind_registry(db) as registry:
            if touch_conversation:
                await registry.chat.finalize_streaming_response(
                    context=system_request_context(user_id),
                    conversation_id=conversation_id,
                    assistant_message_id=assistant_msg_id,
                    content=full_response,
                    now=datetime.now(UTC).replace(tzinfo=None),
                )
            else:
                await registry.chat.update_message_content(
                    context=system_request_context(user_id),
                    conversation_id=conversation_id,
                    message_id=assistant_msg_id,
                    content=full_response,
                )
        await db.commit()
