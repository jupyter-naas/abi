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
import re
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
from naas_abi.apps.nexus.apps.api.app.services.chat.service import render_user_context_block
from naas_abi.apps.nexus.apps.api.app.services.iam.any_workspace import (
    allowed_in_any_workspace,
    require_in_any_workspace,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares
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


def _format_tool_event(chunk: dict) -> str:
    """Render an agent activity event (tool call / result) as markdown so it
    streams visibly into the OpenAI-compatible client (Continue).

    The abi agent runs its tools *server-side*, so we surface them as assistant
    **text** rather than via the OpenAI ``tool_calls`` protocol — the latter would
    make the client believe it must execute the tools itself.
    """
    event = chunk.get("event")
    if event == "tool_usage":
        tool = str(chunk.get("tool") or "").strip()
        return f"\n\n🔧 **{tool}**\n" if tool else ""
    if event == "tool_response":
        out = str(chunk.get("output") or "").strip()
        if not out:
            return ""
        if len(out) > 1000:
            out = out[:1000] + "\n… (truncated)"
        return f"\n```\n{out}\n```\n"
    return ""


def _user_context_preamble(current_user: User, messages: list[ChatMessage]) -> str | None:
    """The caller's profile, for the agent to be told who it is acting for.

    Only the profile half of what Nexus injects can be answered here. The
    skills catalog is scoped to a workspace and an OpenAI chat-completions
    request names none: the credential minted for a coding workspace names its
    user and its sidecar, and nothing in it identifies a Nexus workspace. The note that ships alongside the catalog would be worse than
    absent, because it points at the Skills agent and Settings > Skills, a
    Nexus UI that an editor client does not have.

    The profile is a different matter. ``get_current_user_required`` has
    already turned the bearer token into the full user record before this runs,
    so the tenant was resolved and then dropped.

    First turn only, as in Nexus: a prior assistant message means this thread
    already carries the profile, and the client resends the whole history on
    every turn.
    """
    if any(m.role == "assistant" for m in messages):
        return None
    return render_user_context_block(current_user).strip() or None


async def _stream_agent_text(
    model: str,
    messages: list[ChatMessage],
    thread_id: str,
    ws_base: str | None = None,
    ws_secret: str | None = None,
    user_context_preamble: str | None = None,
) -> AsyncGenerator[str, None]:
    """Invoke an abi agent in-process and yield text deltas only."""
    from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
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
    # Stream the agent's text AND its tool activity (calls + results) as it happens,
    # so the client shows what the agent is doing instead of just the final answer.
    async for chunk in stream_with_abi_inprocess(
        pr_messages, config, thread_id, user_context_preamble=user_context_preamble
    ):
        if isinstance(chunk, str) and chunk:
            yield chunk
        elif isinstance(chunk, dict):
            piece = _format_tool_event(chunk)
            if piece:
                yield piece


def _list_agent_model_ids() -> list[str]:
    """Best-effort list of invokable abi agent names (for /v1/models)."""
    try:
        from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
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
    marker: str = "",
    user_context_preamble: str | None = None,
) -> AsyncGenerator[str, None]:
    yield f"data: {json.dumps(_chunk(completion_id, model, role='assistant'))}\n\n"
    async for delta in _stream_agent_text(
        model, messages, thread_id, ws_base, ws_secret, user_context_preamble
    ):
        yield f"data: {json.dumps(_chunk(completion_id, model, content=delta))}\n\n"
    if marker:
        yield f"data: {json.dumps(_chunk(completion_id, model, content=marker))}\n\n"
    yield f"data: {json.dumps(_chunk(completion_id, model, finish_reason='stop'))}\n\n"
    yield "data: [DONE]\n\n"


# A hidden chat-id marker embedded in each assistant reply. The client (Continue)
# resends prior assistant messages verbatim, so the id round-trips back to us; the
# markdown renderer hides the HTML comment from the user.
_CHAT_MARKER_RE = re.compile(r"<!--\s*abi-chat:([0-9a-f]{8,})\s*-->")


def _chat_marker(chat_id: str) -> str:
    return f"<!-- abi-chat:{chat_id} -->"


def _resolve_chat_id(messages: list[ChatMessage]) -> str:
    """The conversation id, recovered from the marker embedded in a prior reply,
    or a fresh one for a new conversation.

    OpenAI chat-completions requests are stateless and carry no conversation id, so
    we mint one on the first turn and hide it in the reply as an HTML comment. The
    client resends that reply in the history, so on later turns we read it back and
    reuse it as the agent's checkpointer thread — giving each conversation stable,
    collision-free memory, while a brand-new chat (no marker) starts fresh.
    """
    for m in messages:
        if m.role == "assistant" and m.content:
            match = _CHAT_MARKER_RE.search(m.content)
            if match:
                return match.group(1)
    return uuid.uuid4().hex


async def _sidecar_of(user_id: str, sidecar_base: str) -> tuple[str | None, str | None]:
    """The exec sidecar Nexus bound to ``user_id``'s workspace at ``sidecar_base``
    when it provisioned it: ``(base, secret)``, or nothing for an unknown one."""
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.models import CodingEnvironmentModel
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        row = (
            (
                await db.execute(
                    select(CodingEnvironmentModel).where(
                        CodingEnvironmentModel.user_id == user_id,
                        CodingEnvironmentModel.sidecar_base == sidecar_base,
                    )
                )
            )
            .scalars()
            .first()
        )
    if row is None or not row.sidecar_base or not row.sidecar_secret:
        return None, None
    return str(row.sidecar_base), str(row.sidecar_secret)


async def _workspace_target(request: Request) -> tuple[str | None, str | None]:
    """Resolve the caller's coding-workspace sidecar (base URL + secret).

    The coding environment's own credential names its workspace: its key is
    bound to the sidecar (``resource``) when Nexus provisions it, and IAM signs
    that into the token, so the base is server-derived, never client-supplied;
    the secret is the one Nexus stored for that sidecar. Any other credential
    (a session, an API key) names no workspace."""
    from naas_abi.apps.nexus.apps.api.app.services.auth.credentials import CODING

    credential = getattr(request.state, "nexus_credential", None)
    if credential is None or credential.kind != CODING or not credential.resource:
        return None, None
    return await _sidecar_of(credential.user_id, credential.resource)


@router.get(
    "/models",
    dependencies=[
        declares("UseAgent"),
        allowed_in_any_workspace("UseAgent", id="-", feature="chat"),
    ],
)
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


@router.post(
    "/chat/completions",
    response_model=None,
    dependencies=[declares("UseAgent")],
)
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    current_user: User = Depends(get_current_user_required),
) -> StreamingResponse | dict:
    # The agent is the ``model`` of the body, so the check waits for it; a client
    # that names a workspace (``?workspace_id=``) is held to that one.
    await require_in_any_workspace(
        "UseAgent",
        user=current_user,
        workspace=request.query_params.get("workspace_id"),
        id=body.model or "-",
        feature="chat",
    )
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    # Stable per-conversation thread id (recovered from / embedded in the reply)
    # so follow-up turns keep the agent's checkpointer memory.
    chat_id = _resolve_chat_id(body.messages)
    thread_id = f"openai-{chat_id}"
    marker = f"\n\n{_chat_marker(chat_id)}"
    ws_base, ws_secret = await _workspace_target(request)
    preamble = _user_context_preamble(current_user, body.messages)

    if body.stream:
        return StreamingResponse(
            _sse(
                completion_id,
                body.model,
                body.messages,
                thread_id,
                ws_base,
                ws_secret,
                marker,
                preamble,
            ),
            media_type="text/event-stream",
        )

    text = ""
    async for delta in _stream_agent_text(
        body.model, body.messages, thread_id, ws_base, ws_secret, preamble
    ):
        text += delta
    text += marker
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
