from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi.responses import StreamingResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User
from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__dependencies import (
    bind_registry,
    build_provider_messages_with_agents,
    get_or_create_conversation,
    persist_stream_content,
    persist_stream_metadata,
    request_context,
    resolve_provider,
    # run_search_if_needed,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (
    ChatRequest,
)
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


def _format_tool_name(raw: str) -> str:
    words = raw.replace("_", " ").split()
    return " ".join(w[0].upper() + w[1:] for w in words if w)


def _label_tool(raw_tool: str) -> tuple[str, str]:
    """Mirror the frontend ``formatToolLabel`` so server-persisted steps line
    up with what the UI computes locally (``prefix`` is the discriminator the
    analytics renderer keys off)."""
    if raw_tool.startswith("transfer_to"):
        target = raw_tool[len("transfer_to") :].lstrip("_")
        return "Routing to", _format_tool_name(target or raw_tool)
    return "Tool", _format_tool_name(raw_tool)


def _ingest_stream_event_into_steps(
    event_dict: dict[str, Any], steps: list[dict[str, Any]]
) -> None:
    """Apply a single SSE event to the running step accumulator.

    Mirrors the logic in ``chat-interface.tsx`` (``handleToolStartEvent`` /
    ``handleToolResponseEvent`` / ``handleAgentStepEvent``) so the server
    builds the same step list the frontend would build, independently of
    whether the frontend ever sends its final ``PATCH …/metadata``.
    """
    event_name = str(event_dict.get("event") or "").strip()

    if event_name in {"tool", "tool_usage"}:
        raw_tool = str(event_dict.get("tool") or "").strip()
        if not raw_tool:
            return
        input_val = event_dict.get("input")
        input_str = str(input_val) if input_val else None
        prefix, name = _label_tool(raw_tool)
        last = steps[-1] if steps else None
        if (
            last
            and last.get("status") == "running"
            and last.get("_raw_name") == raw_tool
        ):
            if input_str and not last.get("input"):
                last["input"] = input_str
            return
        if last and last.get("status") == "running":
            last["status"] = "done"
        steps.append(
            {
                "tool_name": name,
                "prefix": prefix,
                "status": "running",
                "input": input_str,
                "output": None,
                "_raw_name": raw_tool,
            }
        )
        return

    if event_name == "tool_response":
        output = event_dict.get("output") or event_dict.get("content")
        if not output:
            return
        output_str = str(output).strip()
        if not output_str:
            return
        running_idx = -1
        recent_idx = -1
        for idx in range(len(steps) - 1, -1, -1):
            if steps[idx].get("prefix") == "Tool":
                if recent_idx == -1:
                    recent_idx = idx
                if steps[idx].get("status") == "running":
                    running_idx = idx
                    break
        target_idx = running_idx if running_idx != -1 else recent_idx
        if target_idx == -1:
            return
        steps[target_idx]["status"] = "done"
        steps[target_idx]["output"] = output_str
        return

    if event_name in {"call_model", "agent_calling", "agent_routing"}:
        raw_agent = str(event_dict.get("agent") or "").strip()
        if not raw_agent:
            return
        agent_name = _format_tool_name(raw_agent)
        if not agent_name:
            return
        last = steps[-1] if steps else None
        if last and last.get("status") == "running":
            last["status"] = "done"
        label = (
            "Thinking"
            if event_name in {"call_model", "agent_calling"}
            else f"Routing to {agent_name}"
        )
        steps.append(
            {
                "tool_name": label,
                "prefix": "Agent",
                "status": "running",
                "input": None,
                "output": None,
                "_raw_name": f"{event_name}:{raw_agent}",
            }
        )


def _strip_internal_step_keys(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop server-only bookkeeping fields (e.g. ``_raw_name``) before
    persisting so the shape matches the existing ``MessageStep`` schema and
    the frontend's PATCH payload."""
    return [{k: v for k, v in step.items() if not k.startswith("_")} for step in steps]


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
                # Tag agent-emitted events (AgentToolCalled, AgentAIMessageEmitted, …)
                # with request identity. Set on the request's asyncio context so
                # nested awaits and the Thread spawned by Agent.stream_invoke
                # (which uses copy_context) inherit them.
                from naas_abi_core.services.agent.context import (
                    agent_chat_id,
                    agent_user_id,
                    agent_workspace_id,
                )
                agent_user_id.set(str(current_user.id))
                agent_chat_id.set(str(conversation_id))
                if request.workspace_id is not None:
                    agent_workspace_id.set(str(request.workspace_id))
                provider_messages = await build_provider_messages_with_agents(
                    request=request,
                    context=request_context(current_user),
                    current_agent_id=request.agent,
                    db=db,
                    conversation_id=conversation_id,
                )
                provider_messages, context_sources = registry.chat._inject_chat_vector_context(
                    provider_messages=provider_messages,
                    conversation_id=conversation_id,
                    user_id=current_user.id,
                )
                prior_messages = list(request.messages or [])
                system_prompt = await registry.chat.build_system_prompt(
                    agent=request.agent,
                    explicit_system_prompt=request.system_prompt,
                    prior_messages=prior_messages,
                    user_id=current_user.id,
                )
                user_context_preamble = await registry.chat.build_user_context_addendum(
                    prior_messages=prior_messages,
                    user_id=current_user.id,
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    # search_context = await run_search_if_needed(request)
    # if search_context:
    #     for i in range(len(provider_messages) - 1, -1, -1):
    #         if provider_messages[i].role == "user":
    #             provider_messages[i] = ProviderMessage(
    #                 role="user",
    #                 content=f"{provider_messages[i].content}\n\n---\n{search_context}",
    #                 images=provider_messages[i].images,
    #             )
    #             break

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
        stream_started_at = loop.time()
        # Step accumulator — mirrors the frontend's ``streamToolCalls`` so the
        # tool / agent activity for this turn is captured on the server even
        # if the frontend never PATCHes its final metadata payload.
        steps: list[dict[str, Any]] = []

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
                if isinstance(chunk, str):
                    full_response += chunk
                    buffered_chars += len(chunk)
                    payload = {"content": chunk}
                elif isinstance(chunk, dict):
                    payload = chunk
                    _ingest_stream_event_into_steps(chunk, steps)
                else:
                    continue

                yield_data = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                yield yield_data
                await maybe_flush_incremental()

        async def persist_final_metadata() -> None:
            if not assistant_msg_id:
                return
            # Mark any leftover running steps as done — same finalisation the
            # frontend applies before its PATCH.
            for step in steps:
                if step.get("status") == "running":
                    step["status"] = "done"
            metadata = {
                "execution_time": round(loop.time() - stream_started_at, 3),
                "steps": _strip_internal_step_keys(steps),
                "sources": list(context_sources) if context_sources else [],
            }
            try:
                await persist_stream_metadata(
                    user_id=current_user.id,
                    conversation_id=conversation_id,
                    assistant_msg_id=assistant_msg_id,
                    metadata=metadata,
                )
            except Exception:
                logger.warning("Failed to persist stream metadata", exc_info=True)

        try:
            yield f'data: {{"conversation_id": "{conversation_id}"}}\n\n'
            if context_sources:
                yield f"data: {json.dumps({'sources': context_sources})}\n\n"
            # if search_context:
            #     yield 'data: {"search": true}\n\n'

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
                        user_context_preamble=user_context_preamble,
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
                await persist_final_metadata()

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
                    await persist_final_metadata()
            except Exception:
                logger.warning("Failed to persist partial content on error", exc_info=True)
            yield f'data: {{"error": "{escaped_error}"}}\n\n'
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
