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

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import decode_token
from naas_abi_core.services.agent.context import (
    coder_workspace_base,
    coder_workspace_secret,
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


def _summarize_tool_runs(tool_runs: list[tuple[str | None, str]]) -> str:
    """Build a short confirmation from executed tool calls, used when the agent
    ran tools but returned no closing text of its own."""
    lines = ["Done — completed the requested action(s):", ""]
    for name, output in tool_runs:
        out = output.strip()
        if len(out) > 200:
            out = out[:200] + "…"
        label = f"`{name}`" if name else "tool"
        lines.append(f"- {label}" + (f" → {out}" if out else ""))
    return "\n".join(lines)


async def _stream_agent_text(
    model: str,
    messages: list[ChatMessage],
    thread_id: str,
    ws_base: str | None = None,
    ws_secret: str | None = None,
) -> AsyncGenerator[str, None]:
    """Invoke an abi agent in-process and yield text deltas only."""
    from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (  # noqa: PLC0415
        Message,
        ProviderConfig,
        stream_with_abi_inprocess,
    )

    # Bind the caller's coding workspace so workspace filesystem/terminal tools
    # act on the right container. Set here (the generator's task context) so it
    # propagates into the agent run (asyncio tasks + to_thread inherit context).
    if ws_base:
        coder_workspace_base.set(ws_base)
        coder_workspace_secret.set(ws_secret)

    pr_messages = [Message(role=_coerce_role(m.role), content=m.content) for m in messages]
    config = ProviderConfig(id="abi", name="abi", type="abi", enabled=True, model=model)
    emitted = False
    tool_runs: list[tuple[str | None, str]] = []
    last_tool: str | None = None
    async for chunk in stream_with_abi_inprocess(pr_messages, config, thread_id):
        if isinstance(chunk, str) and chunk:
            emitted = True
            yield chunk
        elif isinstance(chunk, dict):
            event = chunk.get("event")
            if event == "tool_usage":
                last_tool = str(chunk.get("tool") or "") or None
            elif event == "tool_response":
                tool_runs.append((last_tool, str(chunk.get("output") or "")))
                last_tool = None
    # Safety net: the agent acted (ran tools) but produced no closing text. Surface
    # a confirmation so the user always sees what happened instead of a blank reply.
    if not emitted and tool_runs:
        yield _summarize_tool_runs(tool_runs)


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
    completion_id: str,
    model: str,
    messages: list[ChatMessage],
    thread_id: str,
    ws_base: str | None = None,
    ws_secret: str | None = None,
) -> AsyncGenerator[str, None]:
    yield f"data: {json.dumps(_chunk(completion_id, model, role='assistant'))}\n\n"
    async for delta in _stream_agent_text(model, messages, thread_id, ws_base, ws_secret):
        yield f"data: {json.dumps(_chunk(completion_id, model, content=delta))}\n\n"
    yield f"data: {json.dumps(_chunk(completion_id, model, finish_reason='stop'))}\n\n"
    yield "data: [DONE]\n\n"


def _workspace_target(request: Request) -> tuple[str | None, str | None]:
    """Resolve the caller's coding-workspace sidecar (base URL + secret) from
    the bearer token claims injected at provision time. Server-derived only —
    never from a client-supplied field."""
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else ""
    claims = decode_token(token) if token else None
    if not claims:
        return None, None
    return claims.get("ws_base"), claims.get("ws_secret")


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
    request: Request,
    current_user: User = Depends(get_current_user_required),
) -> StreamingResponse | dict:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    thread_id = f"openai-{uuid.uuid4().hex}"
    ws_base, ws_secret = _workspace_target(request)

    if body.stream:
        return StreamingResponse(
            _sse(completion_id, body.model, body.messages, thread_id, ws_base, ws_secret),
            media_type="text/event-stream",
        )

    text = ""
    async for delta in _stream_agent_text(
        body.model, body.messages, thread_id, ws_base, ws_secret
    ):
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
