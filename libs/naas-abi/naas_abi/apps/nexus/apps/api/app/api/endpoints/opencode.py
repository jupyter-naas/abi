"""
Opencode proxy — thin SSE bridge between the Nexus frontend and the local
opencode server.

Uses OpencodeAgent (ABI ecosystem) for auth file bootstrapping and process
management. Additional endpoints proxy opencode's HTTP API directly for
features not exposed by OpencodeAgent (providers, session list/history,
abort, revert, model selection).
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from threading import Lock

import httpx
from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

router = APIRouter(dependencies=[Depends(get_current_user_required)])

# ─── Agent singleton ──────────────────────────────────────────────────────────

_agent = None
_agent_lock = Lock()


def _get_agent():
    """Lazy singleton backed by ABI EngineConfiguration."""
    global _agent
    if _agent is not None:
        return _agent

    with _agent_lock:
        if _agent is not None:
            return _agent

        from naas_abi_core.services.agent.OpencodeAgent import (
            OpencodeAgent,
            OpencodeAgentConfiguration,
        )

        port = None
        workdir = os.environ.get("OPENCODE_WORKDIR") or os.environ.get("FILESYSTEM_ROOT", "/app")
        model = None

        try:
            from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
                EngineConfiguration,
            )
            cfg = EngineConfiguration.load_configuration()
            oc_cfg = getattr(cfg, "opencode", None)
            if oc_cfg is not None:
                port = getattr(oc_cfg, "port", None)
                wd = getattr(oc_cfg, "workdir", None)
                if wd:
                    workdir = str(wd)
                model = getattr(oc_cfg, "model", None)
        except Exception:
            pass

        if port is None:
            port = int(os.environ.get("OPENCODE_PORT", "4005"))

        host = os.environ.get("OPENCODE_HOST", "127.0.0.1")

        _agent = OpencodeAgent(
            configuration=OpencodeAgentConfiguration(
                workdir=workdir,
                port=port,
                host=host,
                name="opencode",
                description="AI coding assistant",
                model=str(model) if model else None,
            )
        )
    return _agent


def _base_url() -> str:
    return _get_agent()._base_url


# ─── Schemas ──────────────────────────────────────────────────────────────────

class OpencodeChatRequest(BaseModel):
    message: str
    session_id: str = ""
    model_provider_id: str = ""
    model_id: str = ""


class OpencodeRevertRequest(BaseModel):
    message_id: str = ""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ensure_session_dir(session_id: str) -> str:
    base = os.environ.get("OPENCODE_WORKDIR") or os.environ.get("FILESYSTEM_ROOT", "/app")
    session_dir = os.path.join(base, session_id)
    os.makedirs(session_dir, exist_ok=True)
    return session_dir


async def _proxy_get(path: str):
    """GET from opencode server and return parsed JSON."""
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.get(f"{_base_url()}/{path}")
        if r.status_code >= 300:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


async def _proxy_post(path: str, body: dict | None = None):
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{_base_url()}/{path}", json=body or {})
        if r.status_code >= 300:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


async def _proxy_delete(path: str):
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.delete(f"{_base_url()}/{path}")
        if r.status_code >= 300:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    try:
        agent = _get_agent()
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{agent._base_url}/global/health")
            ok = r.status_code == 200 and r.json().get("healthy") is True
            return {"healthy": ok, "port": agent.conf.port}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}


@router.get("/providers")
async def providers():
    """List all configured providers and their available models."""
    agent = _get_agent()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, agent.start)
    return await _proxy_get("config/providers")


@router.get("/sessions")
async def list_sessions():
    """List all opencode sessions."""
    agent = _get_agent()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, agent.start)
    return await _proxy_get("session")


@router.get("/sessions/{session_id}/messages")
async def session_messages(session_id: str):
    """Get all messages in a session."""
    return await _proxy_get(f"session/{session_id}/messages")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    return await _proxy_delete(f"session/{session_id}")


@router.post("/sessions/{session_id}/abort")
async def abort_session(session_id: str):
    """Abort a running session (stop mid-stream)."""
    return await _proxy_post(f"session/{session_id}/abort")


@router.post("/sessions/{session_id}/revert")
async def revert_session(session_id: str, body: OpencodeRevertRequest):
    """Revert (undo) the last exchange in a session."""
    payload: dict = {}
    if body.message_id:
        payload["messageID"] = body.message_id
    return await _proxy_post(f"session/{session_id}/revert", payload)


@router.post("/chat")
async def chat(body: OpencodeChatRequest):
    """
    Stream opencode events to the frontend.

    Supports optional model_provider_id / model_id to override the default
    model for this specific message. Each session gets its own sandbox dir.
    """
    agent = _get_agent()
    loop = asyncio.get_running_loop()

    session_id = body.session_id or "default"
    session_dir = _ensure_session_dir(session_id)

    message_with_ctx = (
        f"[Session working directory: {session_dir}]\n\n"
        f"{body.message}"
    )

    # If a model override is specified, bypass astream() and call the HTTP
    # API directly so we can inject model per-message. Otherwise use the
    # standard astream() path which respects EngineConfiguration.
    if body.model_provider_id and body.model_id:
        async def _stream_with_model() -> AsyncIterator[dict]:
            try:
                await loop.run_in_executor(None, agent.start)
                base = _base_url()

                async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=5.0)) as client:
                    # Get or create the opencode session
                    sess_r = await client.get(f"{base}/session/{session_id}")
                    if sess_r.status_code == 200:
                        oc_session_id = sess_r.json().get("id", session_id)
                    else:
                        cr = await client.post(f"{base}/session", json={"title": f"nexus-{session_id}"})
                        cr.raise_for_status()
                        oc_session_id = cr.json().get("id", session_id)

                    # Send the message with model override (non-blocking)
                    prompt_payload = {
                        "parts": [{"type": "text", "text": message_with_ctx}],
                        "model": {"providerID": body.model_provider_id, "modelID": body.model_id},
                    }
                    prompt_task = asyncio.create_task(
                        client.post(f"{base}/session/{oc_session_id}/message", json=prompt_payload)
                    )

                    # Stream events, filtering to this session
                    async with client.stream("GET", f"{base}/event") as resp:
                        async for line in resp.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            raw = line.removeprefix("data:").strip()
                            if not raw:
                                continue
                            try:
                                ev = json.loads(raw)
                            except Exception:
                                continue
                            props = ev.get("properties") or {}
                            if props.get("sessionID") and props["sessionID"] != oc_session_id:
                                continue
                            yield {"data": raw}
                            if ev.get("type") == "session.idle" and props.get("sessionID") == oc_session_id:
                                if not prompt_task.done():
                                    import contextlib
                                    with contextlib.suppress(Exception):
                                        await asyncio.wait_for(asyncio.shield(prompt_task), timeout=3.0)
                                break

            except Exception as exc:
                yield {"data": json.dumps({"type": "error", "message": str(exc)})}
            finally:
                yield {"data": json.dumps({"type": "done"})}

        return EventSourceResponse(_stream_with_model(), media_type="text/event-stream; charset=utf-8")

    # Default path — model from EngineConfiguration
    async def _stream() -> AsyncIterator[dict]:
        try:
            await loop.run_in_executor(None, agent.start)
            async for raw_event in agent.astream(message=message_with_ctx, thread_id=session_id):
                yield {"data": raw_event}
        except Exception as exc:
            yield {"data": json.dumps({"type": "error", "message": str(exc)})}
        finally:
            yield {"data": json.dumps({"type": "done"})}

    return EventSourceResponse(_stream(), media_type="text/event-stream; charset=utf-8")
