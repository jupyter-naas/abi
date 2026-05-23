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


_resolved_opencode_base: str | None = None


def _opencode_base_candidates() -> list[str]:
    port = int(os.environ.get("OPENCODE_PORT", "4005"))
    hosts: list[str] = []
    for host in (
        os.environ.get("OPENCODE_HOST", "127.0.0.1"),
        "host.docker.internal",
        "127.0.0.1",
        "localhost",
    ):
        if host and host not in hosts:
            hosts.append(host)
    return [f"http://{host}:{port}" for host in hosts]


def _sync_agent_from_base(agent: object, base: str) -> None:
    from urllib.parse import urlparse

    parsed = urlparse(base)
    conf = getattr(agent, "conf", None)
    if conf is None:
        return
    conf.host = parsed.hostname or "127.0.0.1"
    conf.port = parsed.port or int(os.environ.get("OPENCODE_PORT", "4005"))


async def _resolve_opencode_base() -> str:
    """Find a reachable opencode server (Docker host, localhost, etc.)."""
    global _resolved_opencode_base

    if _resolved_opencode_base:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                response = await client.get(f"{_resolved_opencode_base}/global/health")
                if response.status_code == 200 and response.json().get("healthy") is True:
                    return _resolved_opencode_base
        except Exception:
            _resolved_opencode_base = None

    last_error = ""
    for base in _opencode_base_candidates():
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{base}/global/health")
                if response.status_code == 200 and response.json().get("healthy") is True:
                    _resolved_opencode_base = base
                    _sync_agent_from_base(_get_agent(), base)
                    return base
        except Exception as exc:
            last_error = str(exc)

    raise HTTPException(
        status_code=503,
        detail=(
            "opencode is not running. On your Mac, run: make opencode-up "
            f"(checked: {', '.join(_opencode_base_candidates())}"
            + (f"; {last_error}" if last_error else "")
            + ")"
        ),
    )


# ─── Schemas ──────────────────────────────────────────────────────────────────

class OpencodeChatRequest(BaseModel):
    message: str
    session_id: str = ""
    model_provider_id: str = ""
    model_id: str = ""
    agent: str = ""  # opencode primary agent, e.g. "build" or "plan"


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
    base = await _resolve_opencode_base()
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.get(f"{base}/{path}")
        if r.status_code >= 300:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


async def _proxy_post(path: str, body: dict | None = None):
    base = await _resolve_opencode_base()
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{base}/{path}", json=body or {})
        if r.status_code >= 300:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


async def _proxy_delete(path: str):
    base = await _resolve_opencode_base()
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.delete(f"{base}/{path}")
        if r.status_code >= 300:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()


def _parse_model_ref(model_value: str | None) -> tuple[str, str] | None:
    if not model_value or "/" not in model_value:
        return None
    provider_id, model_id = model_value.strip().split("/", 1)
    provider_id = provider_id.strip()
    model_id = model_id.strip()
    if provider_id and model_id:
        return provider_id, model_id
    return None


def _lookup_model_name(providers_data: object, provider_id: str, model_id: str) -> str:
    """Resolve a human-readable model name from opencode /config/providers."""
    if not isinstance(providers_data, (list, dict)):
        return model_id

    raw: list[dict] = []
    if isinstance(providers_data, list):
        raw = [p for p in providers_data if isinstance(p, dict)]
    elif isinstance(providers_data, dict):
        nested = providers_data.get("providers")
        if isinstance(nested, list):
            raw = [p for p in nested if isinstance(p, dict)]
        elif isinstance(nested, dict):
            raw = [p for p in nested.values() if isinstance(p, dict)]

    for provider in raw:
        if str(provider.get("id") or "") != provider_id:
            continue
        models = provider.get("models")
        if isinstance(models, dict):
            entry = models.get(model_id)
            if isinstance(entry, dict):
                return str(entry.get("name") or entry.get("id") or model_id)
            return model_id
        if isinstance(models, list):
            for model in models:
                if not isinstance(model, dict):
                    continue
                mid = str(model.get("modelID") or model.get("modelId") or model.get("id") or "")
                if mid == model_id:
                    return str(model.get("name") or mid)
    return model_id


def _first_available_model(providers_data: object) -> tuple[str, str, str] | None:
    if not isinstance(providers_data, (list, dict)):
        return None

    raw: list[dict] = []
    if isinstance(providers_data, list):
        raw = [p for p in providers_data if isinstance(p, dict)]
    elif isinstance(providers_data, dict):
        nested = providers_data.get("providers")
        if isinstance(nested, list):
            raw = [p for p in nested if isinstance(p, dict)]
        elif isinstance(nested, dict):
            raw = [p for p in nested.values() if isinstance(p, dict)]

    for provider in raw:
        provider_id = str(provider.get("id") or "")
        if not provider_id:
            continue
        models = provider.get("models")
        if isinstance(models, dict) and models:
            model_id, entry = next(iter(models.items()))
            if isinstance(entry, dict):
                name = str(entry.get("name") or entry.get("id") or model_id)
            else:
                name = str(model_id)
            return provider_id, str(model_id), name
        if isinstance(models, list):
            for model in models:
                if not isinstance(model, dict):
                    continue
                model_id = str(model.get("modelID") or model.get("modelId") or model.get("id") or "")
                if model_id:
                    name = str(model.get("name") or model_id)
                    return provider_id, model_id, name
    return None


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    try:
        base = await _resolve_opencode_base()
        agent = _get_agent()
        return {"healthy": True, "port": agent.conf.port, "baseUrl": base}
    except HTTPException as exc:
        return {"healthy": False, "error": exc.detail}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}


@router.get("/providers")
async def providers():
    """List all configured providers and their available models."""
    return await _proxy_get("config/providers")


@router.get("/default-model")
async def default_model():
    """Resolved default model (provider/model + display name) for the opencode UI."""
    agent = _get_agent()
    provider_id = ""
    model_id = ""
    name = ""
    source = "auto"

    parsed = _parse_model_ref(agent.conf.model)
    if parsed:
        provider_id, model_id = parsed
        name = model_id
        source = "engine"

    try:
        await _resolve_opencode_base()
        cfg = await _proxy_get("config")
        if isinstance(cfg, dict):
            model_val = cfg.get("model")
            if isinstance(model_val, str):
                cfg_parsed = _parse_model_ref(model_val)
                if cfg_parsed:
                    provider_id, model_id = cfg_parsed
                    name = model_id
                    source = "opencode"

        providers_data = await _proxy_get("config/providers")
        if provider_id and model_id:
            name = _lookup_model_name(providers_data, provider_id, model_id)
        else:
            first = _first_available_model(providers_data)
            if first:
                provider_id, model_id, name = first
    except Exception:
        if not name:
            name = model_id

    return {
        "providerID": provider_id,
        "modelID": model_id,
        "name": name or model_id,
        "source": source,
    }


@router.get("/sessions")
async def list_sessions():
    """List all opencode sessions."""
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

    # Inject skills manifest when sandbox/skills/ has executable scripts.
    # Always use the container-internal FILESYSTEM_ROOT path for reading; OPENCODE_WORKDIR
    # is the host-side path used only by the opencode process itself.
    skills_dir = os.path.join(
        os.environ.get("FILESYSTEM_ROOT", "/app"),
        "sandbox",
        "skills",
    )
    skills_note = ""
    if os.path.isdir(skills_dir):
        skill_files = [
            f for f in os.listdir(skills_dir)
            if f.endswith((".py", ".sh", ".ts", ".js")) and not f.startswith("_")
        ]
        if skill_files:
            skill_entries: list[str] = []
            for fname in sorted(skill_files):
                fpath = os.path.join(skills_dir, fname)
                description = ""
                try:
                    with open(fpath, encoding="utf-8", errors="ignore") as _sf:
                        in_docstring = False
                        for line in _sf:
                            stripped = line.strip()
                            if not in_docstring:
                                if stripped.startswith('"""') or stripped.startswith("'''"):
                                    inner = stripped.strip("\"' ")
                                    if inner:
                                        # inline: """Description."""
                                        description = inner.rstrip('"\'').strip()
                                        break
                                    else:
                                        # opening triple-quote on its own line
                                        in_docstring = True
                                elif stripped and not stripped.startswith("#!") and not stripped.startswith("#"):
                                    break
                            else:
                                if stripped and not stripped.startswith('"""') and not stripped.startswith("'''"):
                                    description = stripped
                                break
                except OSError:
                    pass
                entry = fname if not description else f"{fname} ({description})"
                skill_entries.append(entry)
            skills_note = (
                "\n[Skills in sandbox/skills/ — invoke with bash when the user's request matches: "
                + "; ".join(skill_entries)
                + "]"
            )

    message_with_ctx = (
        f"[Session working directory: {session_dir}]{skills_note}\n\n"
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
                    prompt_payload: dict = {
                        "parts": [{"type": "text", "text": message_with_ctx}],
                        "model": {"providerID": body.model_provider_id, "modelID": body.model_id},
                    }
                    if body.agent:
                        prompt_payload["agent"] = body.agent
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
            oc_agent = body.agent or None
            async for raw_event in agent.astream(
                message=message_with_ctx, thread_id=session_id, agent=oc_agent
            ):
                yield {"data": raw_event}
        except Exception as exc:
            yield {"data": json.dumps({"type": "error", "message": str(exc)})}
        finally:
            yield {"data": json.dumps({"type": "done"})}

    return EventSourceResponse(_stream(), media_type="text/event-stream; charset=utf-8")
