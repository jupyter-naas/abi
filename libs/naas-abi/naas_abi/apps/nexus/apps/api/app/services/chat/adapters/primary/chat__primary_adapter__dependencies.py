from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User
from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.core.postgres_session_registry import PostgresSessionRegistry
from naas_abi.apps.nexus.apps.api.app.services.agents.scopes import scope_resolver
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
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_ingestion import (
    ChatFileIngestionService,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.port import ChatConversationRecord
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import Message as ProviderMessage
from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry, get_service_registry
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from sqlalchemy.ext.asyncio import AsyncSession


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


async def own_conversation(
    chat_service: ChatService,
    current_user: User,
    conversation_id: str,
    action: str,
) -> ChatConversationRecord:
    """The caller's conversation, once IAM allows ``action`` on it.

    A conversation is personal: one that is not the caller's is "not found",
    and the owner is known only after loading it, so routes authorize here.
    """
    row = await chat_service.get_conversation_for_user(
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    if not row:
        # Not the caller's. Someone outside its workspace is told so (403), a
        # member of that workspace only that there is no such conversation.
        other = await chat_service.find_conversation(conversation_id)
        if other is not None:
            await authz.require("GetWorkspace", user=current_user, workspace=other.workspace_id)
        raise HTTPException(status_code=404, detail="Conversation not found")
    await authz.require(
        action,
        user=current_user,
        workspace=row.workspace_id,
        id=(row.user_id, row.id),
    )
    return row


async def conversation_for_file(
    chat_service: ChatService,
    current_user: User,
    conversation_id: str,
    workspace_id: str | None,
    now: datetime,
) -> ChatConversationRecord:
    """The conversation a file is added to, created in ``workspace_id`` when the
    client names one that does not exist yet; ``IngestConversationFile`` either way."""
    row = await chat_service.get_conversation_for_user(
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    if not row:
        if not workspace_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await authz.require(
            "CreateConversation",
            user=current_user,
            workspace=workspace_id,
            id=(current_user.id, conversation_id),
        )
        row = await chat_service.create_conversation(
            user_id=current_user.id,
            workspace_id=workspace_id,
            title="New Conversation",
            agent="aia",
            now=now,
            conversation_id=conversation_id,
        )
    await authz.require(
        "IngestConversationFile",
        user=current_user,
        workspace=row.workspace_id,
        id=(row.user_id, row.id),
    )
    return row


async def authorize_agent_use(
    chat_service: ChatService, current_user: User, agent_id: str | None
) -> None:
    """Using a workspace agent, in the workspace that agent belongs to: its
    module scope (``module:UseAgent``) for a module's agent, ``nexus:UseAgent``
    for one the workspace built.

    A chat turn runs the agent with its workspace's provider settings, so the
    agent's own workspace decides, not the workspace the client names. An id
    that is no workspace agent (an in-process agent named directly) has no row
    to ask about: the in-process runtime runs only the agents the caller may
    use where the turn is stored (``caller_usable_agents``).
    """
    agent = await chat_service.get_agent(agent_id) if agent_id else None
    if agent is None:
        return
    scope = scope_resolver()(agent)
    if scope is not None:
        await authz.require_scope(
            scope, user=current_user, workspace=agent.workspace_id, feature="chat"
        )
        return
    await authz.require(
        "UseAgent",
        user=current_user,
        workspace=agent.workspace_id,
        id=agent.id,
        feature="chat",
    )


async def authorize_turn(
    chat_service: ChatService, request: ChatRequest, current_user: User
) -> None:
    """``SendMessage`` where the turn is stored, ``CreateConversation`` first when
    it opens the conversation, and ``UseAgent`` on the agent it runs.

    With no workspace and no conversation there is nothing to authorize: the
    service refuses the request itself (``workspace_id is required``).
    """
    conversation = (
        await chat_service.get_conversation_for_user(
            user_id=current_user.id, conversation_id=request.conversation_id
        )
        if request.conversation_id
        else None
    )
    if conversation is not None:
        workspaces = {conversation.workspace_id}
        if request.workspace_id:
            # The turn also reads settings of the workspace the client names.
            workspaces.add(request.workspace_id)
        for workspace in sorted(workspaces):
            await authz.require(
                "SendMessage",
                user=current_user,
                workspace=workspace,
                id=(conversation.user_id, conversation.id),
            )
    elif request.workspace_id:
        target = (current_user.id, request.conversation_id or "-")
        for action in ("CreateConversation", "SendMessage"):
            await authz.require(
                action, user=current_user, workspace=request.workspace_id, id=target
            )
    await authorize_agent_use(chat_service, current_user, request.agent)


async def bind_turn_agents(registry: Any, request: ChatRequest, current_user: User) -> None:
    """The agents an in-process turn may run and reach as sub-agents: those the
    caller may use in the workspace the turn is stored in (none without one)."""
    from naas_abi.apps.nexus.apps.api.app.core.agent_feature_access import bind_usable_agents
    from naas_abi_core.services.agent.context import agent_workspace_enabled_class_names

    conversation = (
        await registry.chat.get_conversation_for_user(
            user_id=current_user.id, conversation_id=request.conversation_id
        )
        if request.conversation_id
        else None
    )
    workspace = conversation.workspace_id if conversation is not None else request.workspace_id
    if workspace is None:
        agent_workspace_enabled_class_names.set(frozenset())
        return
    await bind_usable_agents(registry.agents, current_user, workspace)


async def authorize_turn_standalone(request: ChatRequest, current_user: User) -> None:
    """``authorize_turn`` for a route that holds no database session itself."""
    async with AsyncSessionLocal() as db:
        with bind_registry(db) as registry:
            await authorize_turn(registry.chat, request, current_user)


def get_chat_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> ChatService:
    return registry.chat


def get_object_storage_service(request: Request) -> ObjectStorageService:
    storage = getattr(request.app.state, "object_storage", None)
    if storage is not None:
        return storage

    from naas_abi import ABIModule

    module = ABIModule.get_instance()
    storage = module.engine.services.object_storage
    request.app.state.object_storage = storage
    return storage


def get_vector_store_service(request: Request) -> VectorStoreService:
    vector_store = getattr(request.app.state, "vector_store", None)
    if vector_store is not None:
        return vector_store

    from naas_abi import ABIModule

    module = ABIModule.get_instance()
    vector_store = module.engine.services.vector_store
    request.app.state.vector_store = vector_store
    return vector_store


def get_cache_service(request: Request) -> CacheService:
    cache_service = getattr(request.app.state, "cache_service", None)
    if cache_service is not None:
        return cache_service

    from naas_abi import ABIModule

    module = ABIModule.get_instance()
    cache_service = module.engine.services.cache
    request.app.state.cache_service = cache_service
    return cache_service


def get_chat_file_ingestion_service(
    object_storage: ObjectStorageService = Depends(get_object_storage_service),
    vector_store: VectorStoreService = Depends(get_vector_store_service),
    cache_service=Depends(get_cache_service),
) -> ChatFileIngestionService:
    return ChatFileIngestionService(
        object_storage=object_storage,
        vector_store=vector_store,
        cache_service=cache_service,
    )


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
            llm_model=request.provider.llm_model,
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
        regenerate_of=request.regenerate_of,
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
            llm_model=resolved.llm_model,
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
            user_id=current_user.id,
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
    user_id: str,
    current_agent_id: str,
    db: AsyncSession,
    conversation_id: str | None = None,
) -> list[ProviderMessage]:
    with bind_registry(db) as registry:
        return await registry.chat.build_provider_messages_with_agents(
            user_id=user_id,
            request=to_complete_chat_input(request=request),
            current_agent_id=current_agent_id,
            conversation_id=conversation_id,
        )


# async def run_search_if_needed(request: ChatRequest) -> str | None:
#     async with AsyncSessionLocal() as db:
#         with bind_registry(db) as registry:
#             return await registry.chat.run_search_if_needed(
#                 message=request.message,
#                 search_enabled=request.search_enabled,
#             )


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
                    user_id=user_id,
                    conversation_id=conversation_id,
                    assistant_message_id=assistant_msg_id,
                    content=full_response,
                    now=datetime.now(UTC).replace(tzinfo=None),
                )
            else:
                await registry.chat.update_message_content(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id=assistant_msg_id,
                    content=full_response,
                )
        await db.commit()


async def mark_message_superseded(
    user_id: str,
    conversation_id: str,
    message_id: str,
    superseded_by: str,
) -> None:
    """Point a refreshed assistant message at the answer that replaced it.

    Called once the regenerated response is complete, so a failed refresh leaves
    the original answer in place. The superseded row itself is never deleted.
    """
    async with AsyncSessionLocal() as db:
        with bind_registry(db) as registry:
            await registry.chat.mark_message_superseded(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                superseded_by=superseded_by,
            )
        await db.commit()


async def persist_stream_metadata(
    user_id: str,
    conversation_id: str,
    assistant_msg_id: str,
    metadata: dict[str, Any],
) -> None:
    """Write accumulated step metadata for a streaming assistant message.

    Acts as a backend-side safety net: even if the frontend never sends its
    final ``PATCH …/metadata`` call (because the user navigated away or the
    socket dropped), the tool / agent steps observed during the stream still
    end up persisted on ``messages.metadata_`` and remain available to the
    analytics chat detail view.
    """
    async with AsyncSessionLocal() as db:
        with bind_registry(db) as registry:
            await registry.chat.update_message_metadata(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=assistant_msg_id,
                metadata=metadata,
            )
        await db.commit()
