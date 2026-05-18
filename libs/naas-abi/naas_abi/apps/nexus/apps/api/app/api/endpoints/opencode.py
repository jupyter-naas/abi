"""
Opencode proxy — thin SSE bridge between the Nexus frontend and the local
opencode server.

Uses OpencodeAgent (ABI ecosystem) for everything: auth file bootstrapping
from EngineConfiguration, process management, session persistence, model
selection, permission auto-approval.

The only change from the standard OpencodeAgent.astream() is the use of
astream_robust(), which fixes a race condition where session.idle arrives
before the prompt HTTP response — causing astream() to hang indefinitely.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from threading import Lock

from fastapi import APIRouter, Depends
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
        workdir = os.environ.get("FILESYSTEM_ROOT", "/app")
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

        # When the API runs inside Docker, opencode is on the host machine.
        # Set OPENCODE_HOST=host.docker.internal in docker-compose to reach it.
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


# ─── Schemas ──────────────────────────────────────────────────────────────────

class OpencodeChatRequest(BaseModel):
    message: str
    session_id: str = ""


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Check if opencode is reachable."""
    try:
        import httpx
        agent = _get_agent()
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{agent._base_url}/global/health")
            ok = r.status_code == 200 and r.json().get("healthy") is True
            return {"healthy": ok, "port": agent.conf.port}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}


@router.post("/chat")
async def chat(body: OpencodeChatRequest):
    """
    Stream opencode events to the frontend.

    Uses OpencodeAgent.astream_robust() — identical to astream() but waits
    up to 3 s for the prompt task after session.idle, fixing the race where
    session.idle arrives before the HTTP POST response.
    """
    agent = _get_agent()

    # start() is sync/blocking; run in a thread to keep the event loop free
    loop = asyncio.get_running_loop()

    async def _stream() -> AsyncIterator[dict]:
        try:
            await loop.run_in_executor(None, agent.start)

            async for raw_event in agent.astream(
                message=body.message,
                thread_id=body.session_id or None,
            ):
                yield {"data": raw_event}

        except Exception as exc:
            yield {"data": json.dumps({"type": "error", "message": str(exc)})}
        finally:
            yield {"data": json.dumps({"type": "done"})}

    return EventSourceResponse(_stream(), media_type="text/event-stream; charset=utf-8")
