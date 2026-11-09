"""OpenAI-compatible chat completions for a voice engine: speakable sentences only.

Mounted by the module at ``/api/v1/voice``, so TEN's ``openai_llm2_python``
uses ``base_url=<api>/api/v1/voice`` with the caller's Nexus token as
``api_key`` and a per-call ``X-Voice-Session`` header. The same route serves a
speech-to-speech engine's ``ask_abi`` tool (non-streaming).

Unlike the Continue gateway at ``/api/v1/chat/completions``, nothing here is
meant to be read: no tool banners, no fenced output, no hidden chat marker.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import AsyncIterable, AsyncIterator, Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from naas_abi_marketplace.applications.ten_agent.domain.ports import (
    AgentMessage,
    AgentStreamPort,
)
from naas_abi_marketplace.applications.ten_agent.domain.speech import (
    DEFAULT_FILLER,
    speakable,
    voice_preamble,
    voice_thread_id,
)
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    user: str | None = None


def _authenticated_by_api_key(request: Request) -> object:
    header = request.headers.get("Authorization") or ""
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    expected = os.environ.get("ABI_API_KEY")
    if not expected or token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return None


def auth_dependency() -> Callable[..., Any]:
    """Nexus users when Nexus is installed, else the ABI API key."""
    try:
        from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
            get_current_user_required,
        )
    except ImportError:
        return _authenticated_by_api_key
    return get_current_user_required


def _profile(current_user: Any, messages: list[ChatMessage]) -> str | None:
    """The caller's profile, on the first turn only (as Nexus does)."""
    if current_user is None or any(m.role == "assistant" for m in messages):
        return None
    try:
        from naas_abi.apps.nexus.apps.api.app.services.chat.service import (
            render_user_context_block,
        )
    except ImportError:
        return None
    return render_user_context_block(current_user).strip() or None


def _role(role: str) -> Any:
    if role in ("user", "assistant", "system"):
        return role
    return "system" if role == "developer" else "user"


def _chunk(completion_id: str, model: str, **delta: str | None) -> str:
    finish = delta.pop("finish_reason", None)
    body = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {k: v for k, v in delta.items() if v is not None},
                "finish_reason": finish,
            }
        ],
    }
    return f"data: {json.dumps(body)}\n\n"


async def _sse(
    completion_id: str, model: str, deltas: AsyncIterable[str]
) -> AsyncIterator[str]:
    yield _chunk(completion_id, model, role="assistant")
    async for delta in deltas:
        yield _chunk(completion_id, model, content=delta)
    yield _chunk(completion_id, model, finish_reason="stop")
    yield "data: [DONE]\n\n"


def build_router(
    agent_stream: AgentStreamPort,
    *,
    filler: str | None = DEFAULT_FILLER,
    auth: Callable[..., Any] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["voice"])
    current_user_dependency = auth or auth_dependency()

    @router.post("/chat/completions", response_model=None)
    async def voice_chat_completions(
        body: ChatCompletionRequest,
        request: Request,
        current_user: Any = Depends(current_user_dependency),
    ) -> StreamingResponse | dict:
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        user_id = str(getattr(current_user, "id", "") or "api-key")
        session = request.headers.get("x-voice-session") or body.user
        thread_id = voice_thread_id(session, user_id)
        preamble = voice_preamble(_profile(current_user, body.messages))
        messages = [
            AgentMessage(role=_role(m.role), content=m.content) for m in body.messages
        ]
        deltas = speakable(
            agent_stream.stream(body.model, messages, thread_id, preamble), filler
        )
        if body.stream:
            return StreamingResponse(
                _sse(completion_id, body.model, deltas), media_type="text/event-stream"
            )
        text = "".join([d async for d in deltas]).strip()
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

    return router
