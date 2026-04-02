from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi.responses import StreamingResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User
from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__dependencies import (
    bind_registry,
    build_provider_messages_with_agents,
    get_or_create_conversation,
    persist_stream_content,
    request_context,
    resolve_provider,
    run_search_if_needed,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (
    ChatRequest,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.service import AGENT_SYSTEM_PROMPTS
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import Message as ProviderMessage
from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
    ProviderConfig,
    stream_with_abi_inprocess,
    stream_with_cloudflare,
    stream_with_ollama,
)

logger = logging.getLogger(__name__)

OPENAI_COMPATIBLE = [
    "xai",
    "openai",
    "anthropic",
    "mistral",
    "google",
    "openrouter",
    "perplexity",
]
SUPPORTED_STREAMING = ["ollama", "cloudflare", "abi", *OPENAI_COMPATIBLE]

MULTI_AGENT_NOTICE = (
    "\n\n🔄 CRITICAL MULTI-AGENT NOTICE: You are in a conversation where MULTIPLE different AI models "
    "have responded. You are currently responding as the SELECTED agent. Previous assistant responses "
    "may be from DIFFERENT AI agents (Grok, Claude, Qwen, etc.). DO NOT claim authorship of other "
    "agents' responses. DO NOT apologize for what other AIs said. DO NOT correct other AIs' identities. "
    "When asked 'who are you?', ONLY identify yourself based on YOUR model, not what previous agents "
    "said. Each assistant message may be from a different AI - treat them as separate participants."
)


async def stream_chat_response(
    request: ChatRequest,
    current_user: User,
) -> StreamingResponse:
    logger.info(
        "🎯 Stream request: agent=%s, provider=%s",
        request.agent,
        "None" if not request.provider else request.provider.type,
    )

    has_images = bool(request.images) or any(m.images for m in request.messages if m.images)
    provider = await resolve_provider(
        request_context(current_user),
        request.provider,
        has_images,
        request.agent,
        request.workspace_id,
    )

    logger.info(
        "✓ Resolved provider: %s, model=%s",
        provider.type if provider else "None",
        provider.model if provider else "N/A",
    )

    if not provider:

        async def error_stream():
            yield 'data: {"error": "No provider configured. Install Ollama and run: ollama pull qwen3-vl:2b"}\n\n'
            yield "data: [DONE]\n\n"

        return StreamingResponse(error_stream(), media_type="text/event-stream")

    if provider.type not in SUPPORTED_STREAMING:

        async def unsupported_stream():
            yield f'data: {{"error": "Streaming not supported for {provider.type}. Use a different provider type."}}\n\n'
            yield "data: [DONE]\n\n"

        return StreamingResponse(unsupported_stream(), media_type="text/event-stream")

    now = datetime.now(UTC).replace(tzinfo=None)

    async with AsyncSessionLocal() as db:
        try:
            with bind_registry(db) as registry:
                conversation_id = await get_or_create_conversation(
                    chat_service=registry.chat,
                    request=request,
                    current_user=current_user,
                    now=now,
                )
                provider_messages = await build_provider_messages_with_agents(
                    request=request,
                    context=request_context(current_user),
                    current_agent_id=request.agent,
                    db=db,
                    conversation_id=conversation_id,
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    system_prompt = request.system_prompt or AGENT_SYSTEM_PROMPTS.get(
        request.agent, AGENT_SYSTEM_PROMPTS["aia"]
    )
    if request.messages and any(m.role == "assistant" for m in request.messages):
        system_prompt += MULTI_AGENT_NOTICE

    search_context = await run_search_if_needed(request)
    if search_context:
        for i in range(len(provider_messages) - 1, -1, -1):
            if provider_messages[i].role == "user":
                provider_messages[i] = ProviderMessage(
                    role="user",
                    content=f"{provider_messages[i].content}\n\n---\n{search_context}",
                    images=provider_messages[i].images,
                )
                break

    provider_config = ProviderConfig(
        id=provider.id,
        name=provider.name,
        type=provider.type,
        enabled=provider.enabled,
        endpoint=provider.endpoint,
        api_key=provider.api_key,
        account_id=provider.account_id,
        model=provider.model,
    )

    assistant_msg_id = ""
    try:
        async with AsyncSessionLocal() as pre_db:
            with bind_registry(pre_db) as registry:
                _, assistant_msg_id = await registry.chat.create_streaming_message_pair(
                    context=request_context(current_user),
                    conversation_id=conversation_id,
                    user_content=request.message,
                    assistant_agent=request.agent,
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                )
            await pre_db.commit()
    except Exception:
        logger.error("Failed to pre-persist streaming messages", exc_info=True)

    async def generate():
        import asyncio

        full_response = ""
        loop = asyncio.get_running_loop()
        last_flush = loop.time()
        flush_interval_seconds = 0.75
        min_chars_per_flush = 512
        buffered_chars = 0

        async def maybe_flush_incremental() -> None:
            nonlocal last_flush, buffered_chars
            if not assistant_msg_id:
                return
            if (
                buffered_chars < min_chars_per_flush
                and (loop.time() - last_flush) < flush_interval_seconds
            ):
                return
            try:
                await persist_stream_content(
                    user_id=current_user.id,
                    conversation_id=conversation_id,
                    assistant_msg_id=assistant_msg_id,
                    full_response=full_response,
                    touch_conversation=False,
                )
            except Exception:
                logger.warning("Incremental flush failed", exc_info=True)
            last_flush = loop.time()
            buffered_chars = 0

        async def emit_stream(chunks) -> None:
            nonlocal full_response, buffered_chars
            async for chunk in chunks:
                full_response += chunk
                buffered_chars += len(chunk)
                escaped = chunk.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                yield_data = f'data: {{"content": "{escaped}"}}\n\n'
                yield yield_data
                await maybe_flush_incremental()

        try:
            yield f'data: {{"conversation_id": "{conversation_id}"}}\n\n'
            if search_context:
                yield 'data: {"search": true}\n\n'

            if provider.type == "ollama":
                async for output in emit_stream(
                    stream_with_ollama(provider_messages, provider_config, system_prompt)
                ):
                    yield output
            elif provider.type == "cloudflare":
                async for output in emit_stream(
                    stream_with_cloudflare(provider_messages, provider_config, system_prompt)
                ):
                    yield output
            elif provider.type == "abi":
                inprocess_emitted = False
                async for output in emit_stream(
                    stream_with_abi_inprocess(
                        provider_messages,
                        provider_config,
                        thread_id=conversation_id,
                    )
                ):
                    inprocess_emitted = True
                    yield output
                if not inprocess_emitted:
                    raise RuntimeError("In-process ABI stream returned no content")
            elif provider.type in OPENAI_COMPATIBLE:
                from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
                    stream_with_openai_compatible,
                )

                async for output in emit_stream(
                    stream_with_openai_compatible(provider_messages, provider_config, system_prompt)
                ):
                    yield output
            else:
                raise ValueError(f"Streaming not supported for {provider.type}")

            if assistant_msg_id:
                try:
                    await persist_stream_content(
                        user_id=current_user.id,
                        conversation_id=conversation_id,
                        assistant_msg_id=assistant_msg_id,
                        full_response=full_response,
                        touch_conversation=True,
                    )
                except Exception:
                    logger.error("Failed to finalize stream messages to DB", exc_info=True)

            yield "data: [DONE]\n\n"
        except Exception as exc:
            escaped_error = json.dumps(str(exc))[1:-1]
            logger.error(
                "Stream error: %s provider_type=%s provider_name=%s provider_model=%s agent=%s",
                str(exc),
                getattr(provider, "type", None),
                getattr(provider, "name", None),
                getattr(provider, "model", None),
                request.agent,
            )
            try:
                if assistant_msg_id:
                    await persist_stream_content(
                        user_id=current_user.id,
                        conversation_id=conversation_id,
                        assistant_msg_id=assistant_msg_id,
                        full_response=full_response,
                        touch_conversation=True,
                    )
            except Exception:
                logger.warning("Failed to persist partial content on error", exc_info=True)
            yield f'data: {{"error": "{escaped_error}"}}\n\n'
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
