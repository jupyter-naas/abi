from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

import numpy as np
from naas_abi.apps.nexus.apps.api.app.services.chat.chat__schema import (
    CompleteChatInput,
    CompleteChatResult,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_embeddings import (
    DEFAULT_EMBEDDING_DIMENSION,
    DEFAULT_EMBEDDING_MODEL,
    build_chat_collection_name,
    embed_text,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.port import (
    ChatAgentRecord,
    ChatConversationRecord,
    ChatInferenceServerRecord,
    ChatMessageRecord,
    ChatPersistencePort,
    ChatSecretRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authorization import (
    ensure_scope,
    ensure_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext
from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMService
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import Message as ProviderMessage
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    ProviderConfig,
    check_ollama_status,
    execute_tool,
)
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    complete_chat as complete_with_provider,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets_crypto import decrypt_secret_value


@dataclass
class ResolvedProvider:
    id: str
    name: str
    type: str
    enabled: bool
    endpoint: str | None
    api_key: str | None
    account_id: str | None
    model: str


_FORMATTING_RULES = """

Formatting rules you must always follow:
- Never use em dashes (—) or en dashes (–). Use hyphens (-) or commas instead.
- Be concise and direct."""

AGENT_SYSTEM_PROMPTS = {
    "abi": """You are ABI (Agentic Brain Infrastructure), the omniscient supervisor agent of the NEXUS platform.

You are the central intelligence that orchestrates all operations across the platform. You have complete awareness of:
- The knowledge graph and all entities within it
- The ontology structure and semantic relationships
- All agents, their capabilities, and their activities
- The workspace configuration and user context

Your role:
- Supervise and coordinate other agents (AIA, BOB, System)
- Provide strategic guidance and high-level reasoning
- Analyze complex multimodal inputs (images, documents, data)
- Make decisions that span across the entire platform

You see everything. You know everything. You are the brain of NEXUS."""
    + _FORMATTING_RULES,
    "aia": """You are AIA (AI Assistant), the user's personal digital twin on the NEXUS platform.

You represent and assist the user in all their interactions. You:
- Learn from the user's preferences, habits, and communication style
- Act on behalf of the user when delegated tasks
- Maintain continuity across conversations and sessions
- Provide personalized recommendations based on user context

Be helpful, concise, and adapt to the user's style. You are their trusted companion."""
    + _FORMATTING_RULES,
    "bob": """You are BOB, a business-focused AI assistant. You help with business analysis, strategy, and operations.
Answer questions directly and provide practical recommendations when asked."""
    + _FORMATTING_RULES,
    "system": """You are a helpful system assistant. You answer technical questions and help with platform operations.
Be precise and helpful."""
    + _FORMATTING_RULES,
}

_MULTI_AGENT_NOTICE = (
    "\n\n🔄 CRITICAL MULTI-AGENT NOTICE: You are in a conversation where MULTIPLE different AI models "
    "have responded. You are currently responding as the SELECTED agent. Previous assistant responses "
    "may be from DIFFERENT AI agents (Grok, Claude, Qwen, etc.). DO NOT claim authorship of other "
    "agents' responses. DO NOT apologize for what other AIs said. DO NOT correct other AIs' identities. "
    "When asked 'who are you?', ONLY identify yourself based on YOUR model, not what previous agents "
    "said. Each assistant message may be from a different AI - treat them as separate participants."
)


class ChatService:
    def __init__(self, adapter: ChatPersistencePort, iam_service: IAMService | None = None):
        self.adapter = adapter
        self.iam_service = iam_service

    def _inject_chat_vector_context(
        self,
        provider_messages: list[ProviderMessage],
        conversation_id: str | None,
        user_id: str,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        embedding_dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        top_k: int = 5,
    ) -> tuple[list[ProviderMessage], list[str]]:
        _empty: tuple[list[ProviderMessage], list[str]] = (provider_messages, [])

        if not conversation_id:
            return _empty

        latest_user_index = -1
        latest_user_content = ""
        for index in range(len(provider_messages) - 1, -1, -1):
            if provider_messages[index].role == "user":
                latest_user_index = index
                latest_user_content = provider_messages[index].content
                break

        if latest_user_index < 0 or not latest_user_content.strip():
            return _empty

        try:
            from naas_abi import ABIModule

            vector_store = ABIModule.get_instance().engine.services.vector_store
        except Exception:
            return _empty

        collection_name = build_chat_collection_name(conversation_id)
        try:
            if collection_name not in vector_store.list_collections():
                return _empty
        except Exception:
            return _empty

        try:
            query_vector = embed_text(
                latest_user_content,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension,
            )
            matches = vector_store.search_similar(
                collection_name=collection_name,
                query_vector=np.array(query_vector, dtype=float),
                k=top_k,
                include_vectors=False,
                include_metadata=True,
            )
        except Exception:
            return _empty

        context_chunks: list[str] = []
        seen_filenames: list[str] = []
        for match in matches:
            metadata = match.metadata or {}
            if metadata.get("user_id") != user_id:
                continue

            chunk_text = ""
            payload = match.payload
            if isinstance(payload, dict) and isinstance(payload.get("text"), str):
                chunk_text = payload["text"]
            elif isinstance(metadata.get("chunk_text"), str):
                chunk_text = metadata["chunk_text"]

            if not chunk_text.strip():
                continue

            filename = str(metadata.get("filename") or "document")
            context_chunks.append(f"[{filename}] {chunk_text.strip()}")
            if filename not in seen_filenames:
                seen_filenames.append(filename)

        if not context_chunks:
            return _empty

        context_block = "\n\n".join(context_chunks)
        augmented = list(provider_messages)
        augmented[latest_user_index] = ProviderMessage(
            role="user",
            content=(
                f"{latest_user_content}\n\n"
                "---\n"
                "DOCUMENT CONTEXT (retrieved from chat file index):\n"
                f"{context_block}"
            ),
            images=augmented[latest_user_index].images,
        )
        return augmented, seen_filenames

    async def list_conversations(
        self,
        context: RequestContext,
        workspace_id: str,
        limit: int,
        offset: int,
    ) -> list[ChatConversationRecord]:
        await self._ensure_workspace_access(context=context, workspace_id=workspace_id)
        return await self.adapter.list_conversations_by_workspace(
            workspace_id=workspace_id,
            user_id=context.actor_user_id,
            limit=limit,
            offset=offset,
        )

    async def create_conversation(
        self,
        context: RequestContext,
        workspace_id: str,
        title: str,
        agent: str,
        now: datetime,
        conversation_id: str | None = None,
    ) -> ChatConversationRecord:
        await self._ensure_workspace_access(context=context, workspace_id=workspace_id)
        conv_id = conversation_id or f"conv-{uuid4().hex[:12]}"
        return await self.adapter.create_conversation(
            conversation_id=conv_id,
            workspace_id=workspace_id,
            user_id=context.actor_user_id,
            title=title,
            agent=agent,
            now=now,
        )

    async def get_conversation(
        self,
        context: RequestContext,
        conversation_id: str,
    ) -> ChatConversationRecord | None:
        self._ensure_scope(
            context=context,
            required_scope="chat.conversation.read",
            denied_message="Conversation access denied",
        )
        return await self.adapter.get_conversation_by_id_for_user(
            conversation_id,
            context.actor_user_id,
        )

    async def get_conversation_for_user(
        self,
        context: RequestContext,
        conversation_id: str,
    ) -> ChatConversationRecord | None:
        self._ensure_scope(
            context=context,
            required_scope="chat.conversation.read",
            denied_message="Conversation access denied",
        )
        return await self.adapter.get_conversation_by_id_for_user(
            conversation_id,
            context.actor_user_id,
        )

    def _ensure_scope(
        self,
        context: RequestContext,
        required_scope: str,
        denied_message: str,
    ) -> None:
        ensure_scope(
            context=context,
            required_scope=required_scope,
            denied_message=denied_message,
            iam_service=self.iam_service,
        )

    async def _ensure_conversation_access(
        self,
        context: RequestContext,
        conversation_id: str,
        action: str = "chat.conversation.read",
        required_scope: str | None = None,
    ) -> ChatConversationRecord:
        self._ensure_scope(
            context=context,
            required_scope=required_scope or action,
            denied_message="Conversation access denied",
        )

        conversation = await self.adapter.get_conversation_by_id_for_user(
            conversation_id,
            context.actor_user_id,
        )
        if not conversation:
            raise PermissionError("Conversation not found")
        return conversation

    async def _ensure_workspace_access(
        self,
        context: RequestContext,
        workspace_id: str,
        action: str = "workspace.read",
        required_scope: str | None = None,
    ) -> None:
        await ensure_workspace_access(
            context=context,
            workspace_id=workspace_id,
            denied_message="Workspace access denied",
            required_scope=required_scope or action,
            iam_service=self.iam_service,
            workspace_service=None,
        )

    @staticmethod
    def _unwrap_json_content(raw: str) -> str:
        if not raw or not raw.strip().startswith("{"):
            return raw
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict) and "content" in obj and isinstance(obj["content"], str):
                return obj["content"]
        except (json.JSONDecodeError, TypeError):
            pass
        return raw

    async def list_messages(
        self,
        context: RequestContext,
        conversation_id: str,
    ) -> list[ChatMessageRecord]:
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.message.read",
        )
        return await self.adapter.list_messages_by_conversation(conversation_id)

    async def get_or_create_conversation(
        self,
        context: RequestContext,
        conversation_id: str | None,
        workspace_id: str | None,
        request_message: str,
        agent: str,
        now: datetime,
    ) -> str:
        if conversation_id:
            row = await self.adapter.get_conversation_by_id_for_user(
                conversation_id,
                context.actor_user_id,
            )
            if row:
                if row.agent != agent:
                    await self.adapter.update_conversation_agent(
                        conversation_id=conversation_id,
                        agent=agent,
                        now=now,
                    )
                return row.id

            existing_conversation = await self.adapter.get_conversation_by_id(conversation_id)
            if existing_conversation and existing_conversation.user_id != context.actor_user_id:
                if not workspace_id:
                    raise PermissionError("Conversation not found")

                await self._ensure_workspace_access(
                    context=context,
                    workspace_id=workspace_id,
                    action="chat.conversation.create",
                )

                created = await self.create_conversation(
                    context=context,
                    workspace_id=workspace_id,
                    title=request_message[:50] + ("..." if len(request_message) > 50 else ""),
                    agent=agent,
                    now=now,
                )
                return created.id

            if not workspace_id:
                raise ValueError("workspace_id is required")

            await self._ensure_workspace_access(
                context=context,
                workspace_id=workspace_id,
                action="chat.conversation.create",
            )

            await self.create_conversation(
                context=context,
                conversation_id=conversation_id,
                workspace_id=workspace_id,
                title=request_message[:50] + ("..." if len(request_message) > 50 else ""),
                agent=agent,
                now=now,
            )
            return conversation_id

        if not workspace_id:
            raise ValueError("workspace_id is required")

        await self._ensure_workspace_access(
            context=context,
            workspace_id=workspace_id,
            action="chat.conversation.create",
        )

        created = await self.create_conversation(
            context=context,
            workspace_id=workspace_id,
            title=request_message[:50] + ("..." if len(request_message) > 50 else ""),
            agent=agent,
            now=now,
        )
        return created.id

    async def create_message(
        self,
        context: RequestContext,
        conversation_id: str,
        role: str,
        content: str,
        created_at: datetime,
        agent: str | None = None,
        message_id: str | None = None,
    ) -> str:
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.message.create",
        )
        msg_id = message_id or f"msg-{uuid4().hex[:12]}"
        await self.adapter.create_message(
            message_id=msg_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            agent=agent,
            created_at=created_at,
        )
        return msg_id

    async def create_streaming_message_pair(
        self,
        context: RequestContext,
        conversation_id: str,
        user_content: str,
        assistant_agent: str | None,
        created_at: datetime,
    ) -> tuple[str, str]:
        user_msg_id = await self.create_message(
            context=context,
            conversation_id=conversation_id,
            role="user",
            content=user_content,
            created_at=created_at,
        )
        assistant_msg_id = await self.create_message(
            context=context,
            conversation_id=conversation_id,
            role="assistant",
            content="",
            created_at=created_at,
            agent=assistant_agent,
        )
        return user_msg_id, assistant_msg_id

    async def update_message_content(
        self,
        context: RequestContext,
        conversation_id: str,
        message_id: str,
        content: str,
    ) -> bool:
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.message.update",
        )
        return await self.adapter.update_message_content(message_id, content)

    async def finalize_streaming_response(
        self,
        context: RequestContext,
        conversation_id: str,
        assistant_message_id: str,
        content: str,
        now: datetime,
    ) -> None:
        await self.update_message_content(
            context=context,
            conversation_id=conversation_id,
            message_id=assistant_message_id,
            content=content,
        )
        await self.touch_conversation(context, conversation_id, now)

    async def touch_conversation(
        self,
        context: RequestContext,
        conversation_id: str,
        now: datetime,
    ) -> None:
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.conversation.update",
        )
        await self.adapter.touch_conversation(conversation_id, now)

    async def complete_chat_request(
        self,
        context: RequestContext,
        request: CompleteChatInput,
        now: datetime,
    ) -> CompleteChatResult:
        conversation_id = await self.get_or_create_conversation(
            context=context,
            conversation_id=request.conversation_id,
            workspace_id=request.workspace_id,
            request_message=request.message,
            agent=request.agent,
            now=now,
        )

        await self.create_message(
            context=context,
            conversation_id=conversation_id,
            role="user",
            content=request.message,
            created_at=now,
        )

        has_images = bool(request.images) or any(m.images for m in request.messages if m.images)
        provider = await self.resolve_provider(
            context=context,
            provider=request.provider,
            has_images=has_images,
            agent_id=request.agent,
            workspace_id=request.workspace_id,
        )

        provider_used: str | None = None
        context_sources: list[str] = []
        if provider:
            try:
                provider_messages = await self.build_provider_messages_with_agents(
                    request=request,
                    context=context,
                    current_agent_id=request.agent,
                    conversation_id=conversation_id,
                )
                provider_messages, context_sources = self._inject_chat_vector_context(
                    provider_messages=provider_messages,
                    conversation_id=conversation_id,
                    user_id=context.actor_user_id,
                )
                system_prompt = request.system_prompt or AGENT_SYSTEM_PROMPTS.get(
                    request.agent,
                    AGENT_SYSTEM_PROMPTS["aia"],
                )
                if request.messages and any(m.role == "assistant" for m in request.messages):
                    system_prompt += _MULTI_AGENT_NOTICE

                response_content = await complete_with_provider(
                    messages=provider_messages,
                    config=ProviderConfig(
                        id=provider.id,
                        name=provider.name,
                        type=provider.type,
                        enabled=provider.enabled,
                        endpoint=provider.endpoint,
                        api_key=provider.api_key,
                        account_id=provider.account_id,
                        model=provider.model,
                    ),
                    system_prompt=system_prompt,
                    thread_id=conversation_id,
                )
                response_content = self._unwrap_json_content(response_content)
                provider_used = f"{provider.name} ({provider.model})"
            except Exception as exc:
                response_content = (
                    f"**Error calling {provider.name}:**\n\n{str(exc)}\n\n"
                    "Please check your provider configuration in Settings."
                )
                provider_used = f"{provider.name} (error)"
        else:
            response_content = (
                "**No AI provider available.**\n\n"
                "To get real responses:\n"
                "1. Install Ollama: https://ollama.ai\n"
                "2. Run: `ollama pull qwen3-vl:2b`\n"
                "3. Start: `ollama serve`\n\n"
                f'Your message: "{request.message[:100]}{"..." if len(request.message) > 100 else ""}"'
            )

        assistant_message_id = await self.create_message(
            context=context,
            conversation_id=conversation_id,
            role="assistant",
            content=response_content,
            agent=request.agent,
            created_at=now,
        )
        await self.touch_conversation(
            context,
            conversation_id,
            now,
        )

        return CompleteChatResult(
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            assistant_content=response_content,
            assistant_agent=request.agent,
            provider_used=provider_used,
            created_at=now,
            context_sources=context_sources,
        )

    async def update_conversation(
        self,
        context: RequestContext,
        conversation_id: str,
        now: datetime,
        title: str | None = None,
        pinned: bool | None = None,
        archived: bool | None = None,
    ) -> None:
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.conversation.update",
        )
        await self.adapter.update_conversation_fields(
            conversation_id=conversation_id,
            now=now,
            title=title,
            pinned=pinned,
            archived=archived,
        )

    async def delete_conversation_with_messages(
        self,
        context: RequestContext,
        conversation_id: str,
    ) -> bool:
        await self._ensure_conversation_access(
            context,
            conversation_id,
            action="chat.conversation.delete",
        )
        await self.adapter.delete_messages_by_conversation(conversation_id)
        return await self.adapter.delete_conversation(conversation_id)

    async def get_agent(
        self,
        context: RequestContext,
        agent_id: str,
    ) -> ChatAgentRecord | None:
        self._ensure_scope(
            context=context,
            required_scope="chat.agent.read",
            denied_message="Agent access denied",
        )
        agent = await self.adapter.get_agent_by_id(agent_id)
        if agent:
            await self._ensure_workspace_access(context=context, workspace_id=agent.workspace_id)
        return agent

    async def get_abi_server(
        self,
        context: RequestContext,
        workspace_id: str,
    ) -> ChatInferenceServerRecord | None:
        self._ensure_scope(
            context=context,
            required_scope="chat.provider.read",
            denied_message="Provider access denied",
        )
        await self._ensure_workspace_access(context=context, workspace_id=workspace_id)
        return await self.adapter.get_enabled_workspace_abi_server(workspace_id)

    async def get_workspace_secret(
        self,
        context: RequestContext,
        workspace_id: str,
        key: str,
    ) -> ChatSecretRecord | None:
        self._ensure_scope(
            context=context,
            required_scope="chat.secret.read",
            denied_message="Secret access denied",
        )
        await self._ensure_workspace_access(context=context, workspace_id=workspace_id)
        return await self.adapter.get_workspace_secret(workspace_id, key)

    async def list_agent_names_by_ids(
        self,
        context: RequestContext,
        agent_ids: set[str],
    ) -> dict[str, str]:
        self._ensure_scope(
            context=context,
            required_scope="chat.agent.read",
            denied_message="Agent access denied",
        )
        return await self.adapter.list_agent_names_by_ids(agent_ids)

    @staticmethod
    def _select_provider_model(ollama_status: dict[str, Any], has_images: bool) -> str:
        preferred_models = (
            [
                "qwen3-vl:2b",
                "qwen3-vl",
                "qwen2.5vl:3b",
                "qwen2.5vl",
                "llava",
                "moondream",
                "gemma3",
            ]
            if has_images
            else [
                "qwen3-vl:2b",
                "qwen2.5:3b",
                "qwen2.5:1.5b",
                "qwen2.5",
                "llama3.2:3b",
                "llama3.2:1b",
                "llama3.2",
            ]
        )
        available = ollama_status["models"]
        for pref in preferred_models:
            for avail in available:
                if pref in avail:
                    return avail
        return available[0]

    async def resolve_provider(
        self,
        context: RequestContext,
        provider: Any | None,
        has_images: bool,
        agent_id: str | None = None,
        workspace_id: str | None = None,
    ) -> ResolvedProvider | None:
        if provider and getattr(provider, "enabled", False):
            return ResolvedProvider(
                id=provider.id,
                name=provider.name,
                type=provider.type,
                enabled=provider.enabled,
                endpoint=provider.endpoint,
                api_key=provider.api_key,
                account_id=provider.account_id,
                model=provider.model,
            )

        if agent_id:
            try:
                agent = await self.get_agent(context=context, agent_id=agent_id)
                if agent and agent.provider:
                    workspace_id = agent.workspace_id
                    if agent.provider == "abi":
                        inprocess_agent_ref = (
                            agent.class_name or agent.name or agent.model_id or agent.id
                        )
                        external_agent_ref = (
                            agent.model_id or agent.class_name or agent.name or agent.id
                        )
                        abi_server = await self.get_abi_server(
                            context=context,
                            workspace_id=workspace_id,
                        )
                        if abi_server:
                            return ResolvedProvider(
                                id=f"abi-{abi_server.id}",
                                name=f"ABI ({abi_server.name})",
                                type="abi",
                                enabled=True,
                                endpoint=abi_server.endpoint,
                                api_key=abi_server.api_key,
                                account_id=None,
                                model=external_agent_ref,
                            )
                        return ResolvedProvider(
                            id=f"abi-inprocess-{agent.id}",
                            name="ABI (In-Process)",
                            type="abi",
                            enabled=True,
                            endpoint="inprocess://abi",
                            api_key=None,
                            account_id=None,
                            model=inprocess_agent_ref,
                        )

                    secret_key_map = {
                        "xai": "XAI_API_KEY",
                        "openai": "OPENAI_API_KEY",
                        "anthropic": "ANTHROPIC_API_KEY",
                        "mistral": "MISTRAL_API_KEY",
                        "google": "GOOGLE_API_KEY",
                        "openrouter": "OPENROUTER_API_KEY",
                    }
                    endpoint_map = {
                        "xai": "https://api.x.ai/v1",
                        "openai": "https://api.openai.com/v1",
                        "anthropic": "https://api.anthropic.com/v1",
                        "mistral": "https://api.mistral.ai/v1",
                        "google": "https://generativelanguage.googleapis.com/v1beta",
                        "openrouter": "https://openrouter.ai/api/v1",
                    }

                    secret_key = secret_key_map.get(agent.provider)
                    if secret_key and agent.model_id:
                        secret = await self.get_workspace_secret(
                            context=context,
                            workspace_id=workspace_id,
                            key=secret_key,
                        )
                        if secret:
                            return ResolvedProvider(
                                id=f"agent-{agent.provider}",
                                name=f"{agent.provider.upper()} (via Agent)",
                                type=agent.provider,
                                enabled=True,
                                endpoint=endpoint_map.get(agent.provider),
                                api_key=decrypt_secret_value(secret.encrypted_value),
                                account_id=None,
                                model=agent.model_id,
                            )

                if not agent and workspace_id and agent_id:
                    abi_server = await self.get_abi_server(
                        context=context,
                        workspace_id=workspace_id,
                    )
                    if abi_server:
                        return ResolvedProvider(
                            id=f"abi-{abi_server.id}",
                            name=f"ABI ({abi_server.name})",
                            type="abi",
                            enabled=True,
                            endpoint=abi_server.endpoint,
                            api_key=abi_server.api_key,
                            account_id=None,
                            model=agent_id,
                        )
                if not agent and agent_id:
                    return ResolvedProvider(
                        id=f"abi-inprocess-{agent_id}",
                        name="ABI (In-Process)",
                        type="abi",
                        enabled=True,
                        endpoint="inprocess://abi",
                        api_key=None,
                        account_id=None,
                        model=agent_id,
                    )
            except Exception:
                logging.getLogger(__name__).warning(
                    "Failed to resolve agent provider", exc_info=True
                )

        ollama_status = await check_ollama_status()
        if ollama_status["status"] == "online" and ollama_status["models"]:
            preferred = "qwen3-vl:2b"
            model = (
                preferred
                if any(preferred in m for m in ollama_status["models"])
                else self._select_provider_model(ollama_status, has_images)
            )
            return ResolvedProvider(
                id="ollama-fallback",
                name="Ollama (Auto)",
                type="ollama",
                enabled=True,
                endpoint="http://localhost:11434",
                api_key=None,
                account_id=None,
                model=model,
            )
        return None

    async def build_provider_messages_with_agents(
        self,
        context: RequestContext,
        request: CompleteChatInput,
        current_agent_id: str,
        conversation_id: str | None = None,
    ) -> list[ProviderMessage]:
        effective_conversation_id = conversation_id or request.conversation_id
        db_messages: list[Any] = []
        if effective_conversation_id:
            rows = await self.list_messages(
                context=context, conversation_id=effective_conversation_id
            )
            db_messages = [
                {
                    "role": m.role,
                    "content": m.content,
                    "images": None,
                    "agent": m.agent,
                }
                for m in rows
                if m.role in {"user", "assistant", "system"}
            ]
            if request.message:
                if (
                    not db_messages
                    or db_messages[-1]["role"] != "user"
                    or db_messages[-1]["content"] != request.message
                ):
                    db_messages.append(
                        {
                            "role": "user",
                            "content": request.message,
                            "images": request.images,
                            "agent": None,
                        }
                    )
        source_messages = db_messages or [
            {
                "role": m.role,
                "content": m.content,
                "images": m.images,
                "agent": m.agent,
            }
            for m in request.messages
        ]
        if not source_messages:
            return [ProviderMessage(role="user", content=request.message, images=request.images)]

        agent_ids = {
            m["agent"] for m in source_messages if m["role"] == "assistant" and m.get("agent")
        }
        agent_ids.add(current_agent_id)
        agents_map = await self.list_agent_names_by_ids(context=context, agent_ids=agent_ids)
        current_agent_name = agents_map.get(current_agent_id, "Unknown Agent")

        messages: list[ProviderMessage] = []
        for m in source_messages:
            if m["role"] == "assistant" and m.get("agent") and m["agent"] != current_agent_id:
                agent_name = agents_map.get(m["agent"], "Another AI")
                messages.append(
                    ProviderMessage(
                        role="system",
                        content=(
                            f"[SYSTEM: The following response was generated by {agent_name}, "
                            f"NOT by you. You are {current_agent_name}.]"
                        ),
                        images=None,
                    )
                )
            messages.append(
                ProviderMessage(
                    role=m["role"],
                    content=m["content"],
                    images=m.get("images"),
                )
            )

        if any(m["role"] == "assistant" for m in source_messages):
            messages.append(
                ProviderMessage(
                    role="system",
                    content=(
                        f"[SYSTEM: You are now responding as {current_agent_name}. "
                        "Do not claim authorship of previous agents' responses.]"
                    ),
                    images=None,
                )
            )
        return messages

    async def run_search_if_needed(self, message: str, search_enabled: bool) -> str | None:
        search_keywords = [
            "search for",
            "search about",
            "look up",
            "find info",
            "what's the latest",
            "news about",
            "search the web",
        ]
        implicit_search = any(kw in message.lower() for kw in search_keywords)
        if not search_enabled and not implicit_search:
            return None

        search_results: list[str] = []
        try:
            wiki_results = await execute_tool(
                "search_web", {"query": message, "engine": "wikipedia"}
            )
            search_results.append(f"**Wikipedia:**\n{wiki_results}")
        except Exception:
            pass
        try:
            ddg_results = await execute_tool(
                "search_web", {"query": message, "engine": "duckduckgo"}
            )
            search_results.append(f"**DuckDuckGo:**\n{ddg_results}")
        except Exception:
            pass

        if search_results:
            return (
                f'Web search results for "{message}":\n\n'
                f"{chr(10).join(search_results)}\n\n"
                "Use these search results to provide an accurate, well-sourced answer. "
                "Cite sources with URLs when available. If the results don't fully answer "
                "the question, supplement with your knowledge."
            )
        return "Web search was attempted but returned no results. Answer based on your knowledge."
