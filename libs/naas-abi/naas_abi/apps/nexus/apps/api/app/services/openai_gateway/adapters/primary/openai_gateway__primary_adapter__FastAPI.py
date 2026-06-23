"""OpenAI-compatible shim over abi agents.

Exposes a minimal OpenAI Chat Completions surface (`/v1/chat/completions`,
`/v1/models`) that maps onto abi's in-process agent invocation. This lets the
Continue VS Code extension (or any OpenAI-compatible client) inside a coding
workspace talk to abi agents: the OpenAI ``model`` field is the abi agent name.

Auth is the normal Nexus bearer token (the workspace is provisioned with a
per-user token). The agent-invocation and agent-listing are kept as module-level
functions (`_stream_agent_text`, `_list_agent_model_ids`) so the OpenAI
translation layer is unit-testable without running a real agent.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from pydantic import BaseModel

router = APIRouter(dependencies=[Depends(get_current_user_required)])

_ALLOWED_ROLES = {"user", "assistant", "system"}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    # Accepted for OpenAI compatibility; currently advisory only.
    temperature: float | None = None
    max_tokens: int | None = None
    user: str | None = None


def _coerce_role(role: str) -> str:
    if role in _ALLOWED_ROLES:
        return role
    if role == "developer":
        return "system"
    return "user"


async def _stream_agent_text(
    model: str, messages: list[ChatMessage], thread_id: str
) -> AsyncGenerator[str, None]:
    """Invoke an abi agent in-process and yield text deltas only."""
    from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (  # noqa: PLC0415
        Message,
        ProviderConfig,
        stream_with_abi_inprocess,
    )

    pr_messages = [Message(role=_coerce_role(m.role), content=m.content) for m in messages]
    config = ProviderConfig(id="abi", name="abi", type="abi", enabled=True, model=model)
    async for chunk in stream_with_abi_inprocess(pr_messages, config, thread_id):
        if isinstance(chunk, str) and chunk:
            yield chunk


def _list_agent_model_ids() -> list[str]:
    """Best-effort list of invokable abi agent names (for /v1/models)."""
    try:
        from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (  # noqa: PLC0415
            _build_local_agent_index,
        )

        _, hints = _build_local_agent_index()
        names = sorted({hint.split("/")[-1] for hint in hints if hint})
        return names or ["aia"]
    except Exception:
        return ["aia"]


def _chunk(
    completion_id: str,
    model: str,
    *,
    role: str | None = None,
    content: str | None = None,
    finish_reason: str | None = None,
) -> dict:
    delta: dict[str, str] = {}
    if role is not None:
        delta["role"] = role
    if content is not None:
        delta["content"] = content
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


async def _sse(
    completion_id: str, model: str, messages: list[ChatMessage], thread_id: str
) -> AsyncGenerator[str, None]:
    yield f"data: {json.dumps(_chunk(completion_id, model, role='assistant'))}\n\n"
    async for delta in _stream_agent_text(model, messages, thread_id):
        yield f"data: {json.dumps(_chunk(completion_id, model, content=delta))}\n\n"
    yield f"data: {json.dumps(_chunk(completion_id, model, finish_reason='stop'))}\n\n"
    yield "data: [DONE]\n\n"


@router.get("/models")
async def list_models(
    current_user: User = Depends(get_current_user_required),
) -> dict:
    model_ids = await run_in_threadpool(_list_agent_model_ids)
    created = int(time.time())
    return {
        "object": "list",
        "data": [
            {"id": model_id, "object": "model", "created": created, "owned_by": "abi"}
            for model_id in model_ids
        ],
    }


@router.post("/chat/completions", response_model=None)
async def chat_completions(
    body: ChatCompletionRequest,
    current_user: User = Depends(get_current_user_required),
) -> StreamingResponse | dict:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    thread_id = f"openai-{uuid.uuid4().hex}"

    if body.stream:
        return StreamingResponse(
            _sse(completion_id, body.model, body.messages, thread_id),
            media_type="text/event-stream",
        )

    text = ""
    async for delta in _stream_agent_text(body.model, body.messages, thread_id):
        text += delta
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
