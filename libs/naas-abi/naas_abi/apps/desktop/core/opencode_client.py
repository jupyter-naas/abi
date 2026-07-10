"""Minimal standalone opencode client for ABI Desktop.

Talks to a local ``opencode serve`` process over HTTP/SSE. Unlike
``naas_abi_core.services.agent.OpencodeAgent`` this has zero langchain /
engine dependencies so it can be bundled into a small executable.

Protocol (opencode >= 1.x, same endpoints the Nexus integration uses):

- ``GET  /global/health``                          readiness probe
- ``POST /session``                                create session
- ``POST /session/{id}/message``                   send prompt
- ``GET  /event``                                  global SSE event stream
- ``GET  /config/providers``                       available models
- ``POST /session/{id}/abort``                     stop a running prompt
- ``POST /session/{id}/permissions/{permission}``  approve tool permission
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import json
import shlex
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from ..config.desktop_config import build_shell_env_source
from .model_capabilities import provider_model_supports_tools


class OpencodeUnavailableError(Exception):
    pass


def _resolve_opencode_bin(bin_name: str) -> str:
    """Resolve a bare binary name to an absolute path for subprocess spawn.

    ``bash -lc`` may pick a different ``PATH`` entry than Python's
    :func:`shutil.which`; spawning the resolved path avoids a stale wrapper
    (e.g. ``/usr/local/bin/opencode``) that never becomes healthy.
    """
    if "/" in bin_name or bin_name.startswith("."):
        return str(Path(bin_name).expanduser())
    return shutil.which(bin_name) or bin_name


class OpencodeClient:
    def __init__(
        self,
        workdir: str,
        opencode_bin: str = "opencode",
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        """Client for a local ``opencode serve`` HTTP API.

        By default the client owns the process: :meth:`start` spawns
        ``opencode serve`` on a free port. Passing ``base_url`` attaches to
        an existing endpoint instead (no process is spawned). ``transport``
        overrides the httpx transport for the async API — with e.g.
        ``httpx.ASGITransport`` requests go to an in-process app, which is
        the seam used by tests.
        """
        self.workdir = workdir
        self.opencode_bin = _resolve_opencode_bin(opencode_bin)
        self.port: int | None = None
        self._base_url = base_url
        self._transport = transport
        self._proc: subprocess.Popen[bytes] | None = None
        atexit.register(self.stop)

    @property
    def base_url(self) -> str:
        if self._base_url is not None:
            return self._base_url
        if self.port is None:
            raise OpencodeUnavailableError("opencode is not running")
        return f"http://127.0.0.1:{self.port}"

    def _client(self, timeout: httpx.Timeout | float) -> httpx.AsyncClient:
        # Only pass transport when injected so callers monkeypatching
        # httpx.AsyncClient defaults (e.g. tests) are not overridden.
        if self._transport is not None:
            return httpx.AsyncClient(timeout=timeout, transport=self._transport)
        return httpx.AsyncClient(timeout=timeout)

    # -- lifecycle ------------------------------------------------------

    def is_running(self) -> bool:
        if self._transport is not None:
            # Injected transports (in-process apps) are always reachable.
            return True
        if self._base_url is None and self.port is None:
            return False
        try:
            response = httpx.get(f"{self.base_url}/global/health", timeout=1.0)
            payload = response.json()
            return response.status_code == 200 and payload.get("healthy") is True
        except Exception:
            return False

    def start(self, startup_timeout: float = 45.0) -> None:
        if self.is_running():
            return

        self.port = _find_free_port()
        command = (
            f"{build_shell_env_source(self.workdir)} "
            f"{shlex.quote(self.opencode_bin)} serve --port {self.port}"
        )
        self._proc = subprocess.Popen(
            ["bash", "-lc", command],
            cwd=self.workdir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        deadline = time.monotonic() + startup_timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise OpencodeUnavailableError(
                    f"opencode exited during startup (bin: {self.opencode_bin})"
                )
            if self.is_running():
                return
            time.sleep(0.25)

        self.stop()
        raise OpencodeUnavailableError(
            f"opencode did not become ready within {startup_timeout}s"
        )

    def stop(self) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        self.port = None

    def restart(
        self, workdir: str | None = None, opencode_bin: str | None = None
    ) -> None:
        self.stop()
        if workdir:
            self.workdir = workdir
        if opencode_bin:
            self.opencode_bin = _resolve_opencode_bin(opencode_bin)
        self.start()

    # -- sessions / models ------------------------------------------------

    async def create_session(self, title: str) -> str:
        async with self._client(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/session", json={"title": title}
            )
            response.raise_for_status()
            payload = response.json()
        session_id = (
            payload.get("id")
            or payload.get("session", {}).get("id")
            or payload.get("session_id")
        )
        if not session_id:
            raise OpencodeUnavailableError("opencode did not return a session id")
        return str(session_id)

    async def providers(self) -> list[dict[str, Any]]:
        async with self._client(timeout=15.0) as client:
            response = await client.get(f"{self.base_url}/config/providers")
            response.raise_for_status()
            payload = response.json()

        raw_providers = payload.get("providers", payload)
        if isinstance(raw_providers, dict):
            raw_providers = list(raw_providers.values())
        if not isinstance(raw_providers, list):
            return []

        providers: list[dict[str, Any]] = []
        for provider in raw_providers:
            if not isinstance(provider, dict):
                continue
            models = provider.get("models") or {}
            provider_id = str(provider.get("id") or "")
            if isinstance(models, dict):
                model_list = [
                    {
                        "id": model_id,
                        "name": (m or {}).get("name") or model_id,
                        "supports_tools": provider_model_supports_tools(
                            provider_id, model_id
                        ),
                    }
                    for model_id, m in models.items()
                ]
            elif isinstance(models, list):
                model_list = [
                    {
                        "id": m.get("id"),
                        "name": m.get("name") or m.get("id"),
                        "supports_tools": provider_model_supports_tools(
                            provider_id, str(m.get("id") or "")
                        ),
                    }
                    for m in models
                    if isinstance(m, dict) and m.get("id")
                ]
            else:
                model_list = []
            providers.append(
                {
                    "id": provider.get("id"),
                    "name": provider.get("name") or provider.get("id"),
                    "models": model_list,
                }
            )
        return providers

    async def abort(self, session_id: str) -> None:
        async with self._client(timeout=10.0) as client:
            await client.post(f"{self.base_url}/session/{session_id}/abort")

    # -- prompting ----------------------------------------------------------

    async def stream_message(
        self,
        session_id: str,
        text: str,
        model: str | None = None,
        agent: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Send a prompt and yield normalized events until the session idles.

        Yields dicts of shape:
        - ``{"type": "text", "text": str, "part_id": str}`` cumulative text part
        - ``{"type": "reasoning"}``
        - ``{"type": "tool", "tool": str, "status": str, "title": str}``
        - ``{"type": "error", "message": str}``
        - ``{"type": "complete", "text": str}`` final assistant text
        """
        payload: dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        model_payload = _model_payload(model)
        if model_payload:
            payload["model"] = model_payload
        if agent:
            payload["agent"] = agent

        timeout = httpx.Timeout(connect=10.0, write=60.0, read=None, pool=60.0)
        approved_permissions: set[str] = set()
        seen_tool_states: set[str] = set()
        assistant_message_ids: set[str] = set()
        part_types: dict[str, str] = {}
        text_buffers: dict[str, str] = {}
        saw_assistant_activity = False
        seen_errors: set[str] = set()

        async with self._client(timeout=timeout) as client:
            prompt_task = asyncio.create_task(
                client.post(
                    f"{self.base_url}/session/{session_id}/message", json=payload
                )
            )

            try:
                async with client.stream("GET", f"{self.base_url}/event") as response:
                    if response.status_code >= 300:
                        body = await response.aread()
                        yield {
                            "type": "error",
                            "message": body.decode(errors="replace"),
                        }
                        return

                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line.removeprefix("data:").strip()
                        if not data:
                            continue
                        try:
                            event = json.loads(data)
                        except Exception:
                            continue
                        if not isinstance(event, dict):
                            continue

                        properties = event.get("properties") or {}
                        event_session = properties.get("sessionID")
                        if event_session and event_session != session_id:
                            continue

                        for permission_id in _collect_permission_ids(event):
                            if permission_id in approved_permissions:
                                continue
                            if await _approve_permission(
                                client, self.base_url, session_id, permission_id
                            ):
                                approved_permissions.add(permission_id)

                        event_type = str(event.get("type") or "")
                        if event_type == "message.part.updated":
                            part = properties.get("part") or {}
                            if isinstance(part, dict):
                                part_id = str(part.get("id") or "")
                                part_type = str(part.get("type") or "")
                                if part_id and part_type:
                                    part_types[part_id] = part_type
                        if event_type == "message.updated":
                            info = properties.get("info") or {}
                            if info.get("role") == "assistant" and info.get("id"):
                                assistant_message_ids.add(str(info["id"]))
                                saw_assistant_activity = True
                            error_message = _extract_session_error(info.get("error"))
                            if error_message and error_message not in seen_errors:
                                seen_errors.add(error_message)
                                yield {"type": "error", "message": error_message}
                        elif event_type == "session.error":
                            error_message = _extract_session_error(
                                properties.get("error") or properties
                            )
                            if error_message and error_message not in seen_errors:
                                seen_errors.add(error_message)
                                yield {"type": "error", "message": error_message}
                        elif event_type == "message.part.delta":
                            part_id = str(properties.get("partID") or "")
                            message_id = str(properties.get("messageID") or "")
                            field = str(properties.get("field") or "")
                            delta = properties.get("delta")
                            if (
                                part_id
                                and field == "text"
                                and isinstance(delta, str)
                                and part_types.get(part_id) == "text"
                                and (
                                    not message_id
                                    or not assistant_message_ids
                                    or message_id in assistant_message_ids
                                )
                            ):
                                text_buffers[part_id] = (
                                    text_buffers.get(part_id, "") + delta
                                )
                                yield {
                                    "type": "text",
                                    "text": text_buffers[part_id],
                                    "part_id": part_id,
                                }
                                continue

                        normalized = _normalize_event(
                            event, seen_tool_states, assistant_message_ids
                        )
                        if normalized:
                            yield normalized

                        if (
                            event.get("type") == "session.idle"
                            and properties.get("sessionID") == session_id
                        ):
                            if prompt_task.done():
                                break
                            # Race: the session can go idle before the prompt
                            # POST resolves. Once we've seen assistant output,
                            # idle means the turn is over — give the response
                            # a grace window instead of waiting forever.
                            if saw_assistant_activity:
                                with contextlib.suppress(asyncio.TimeoutError):
                                    await asyncio.wait_for(
                                        asyncio.shield(prompt_task), timeout=15.0
                                    )
                                break

                response_payload: dict[str, Any] = {}
                try:
                    prompt_response = await asyncio.wait_for(
                        asyncio.shield(prompt_task), timeout=15.0
                    )
                except asyncio.TimeoutError:
                    # Streamed text already reached the caller; finish the turn.
                    yield {"type": "complete", "text": ""}
                    return
                if prompt_response.status_code < 300:
                    try:
                        parsed = prompt_response.json()
                        if isinstance(parsed, dict):
                            response_payload = parsed
                    except ValueError:
                        pass
                    error_message = _extract_session_error(
                        (response_payload.get("info") or {}).get("error")
                    )
                    if error_message and error_message not in seen_errors:
                        seen_errors.add(error_message)
                        yield {"type": "error", "message": error_message}
                else:
                    yield {
                        "type": "error",
                        "message": f"opencode returned {prompt_response.status_code}: "
                        f"{prompt_response.text[:500]}",
                    }

                yield {"type": "complete", "text": _extract_text(response_payload)}
            finally:
                if not prompt_task.done():
                    prompt_task.cancel()


def _model_payload(model: str | None) -> dict[str, str] | None:
    if not model or "/" not in model:
        return None
    provider_id, model_id = model.split("/", 1)
    provider_id, model_id = provider_id.strip(), model_id.strip()
    if not provider_id or not model_id:
        return None
    return {"providerID": provider_id, "modelID": model_id}


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _collect_permission_ids(event: dict[str, Any]) -> set[str]:
    found: set[str] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                _walk(item)
        elif isinstance(value, list):
            for item in value:
                _walk(item)
        elif isinstance(value, str) and value.startswith("per_"):
            found.add(value)

    _walk(event)
    return found


async def _approve_permission(
    client: httpx.AsyncClient, base_url: str, session_id: str, permission_id: str
) -> bool:
    for body in ({"response": "always"}, {"response": "once"}):
        try:
            response = await client.post(
                f"{base_url}/session/{session_id}/permissions/{permission_id}",
                json=body,
            )
            if response.status_code < 300:
                return True
        except Exception:
            continue
    return False


def _extract_session_error(error: Any) -> str:
    if not isinstance(error, dict) or not error:
        return ""
    data = error.get("data")
    if isinstance(data, dict):
        message = data.get("message")
        if isinstance(message, str) and message:
            return message
    name = error.get("name")
    if isinstance(name, str) and name:
        return name
    return ""


def _normalize_event(
    event: dict[str, Any],
    seen_tool_states: set[str],
    assistant_message_ids: set[str],
) -> dict[str, Any] | None:
    if event.get("type") != "message.part.updated":
        return None

    part = (event.get("properties") or {}).get("part") or {}
    if not isinstance(part, dict):
        return None

    part_type = part.get("type")
    if part_type == "text":
        # User prompts echo through the same event stream; only forward
        # parts belonging to assistant messages.
        if str(part.get("messageID") or "") not in assistant_message_ids:
            return None
        text = part.get("text")
        if isinstance(text, str):
            return {"type": "text", "text": text, "part_id": str(part.get("id") or "")}
        return None

    if part_type == "reasoning":
        return {"type": "reasoning"}

    if part_type == "tool":
        state = part.get("state") or {}
        if not isinstance(state, dict):
            return None
        status = str(state.get("status") or "")
        tool = str(part.get("tool") or "tool")
        dedupe = f"{part.get('callID') or part.get('id')}:{status}"
        if dedupe in seen_tool_states:
            return None
        seen_tool_states.add(dedupe)
        title = ""
        if isinstance(state.get("title"), str):
            title = state["title"]
        elif isinstance(state.get("input"), dict):
            input_payload = state["input"]
            title = str(
                input_payload.get("filePath")
                or input_payload.get("command")
                or input_payload.get("pattern")
                or ""
            )
        return {
            "type": "tool",
            "tool": tool,
            "status": status,
            "title": title[:200],
            "call_id": str(part.get("callID") or part.get("id") or ""),
        }

    return None


def _extract_text(payload: dict[str, Any]) -> str:
    parts = payload.get("parts")
    if not isinstance(parts, list):
        message = payload.get("message")
        if isinstance(message, dict) and isinstance(message.get("parts"), list):
            parts = message["parts"]
        else:
            parts = []

    chunks: list[str] = []
    for part in parts:
        if isinstance(part, dict) and part.get("type") == "text":
            text = part.get("text")
            if isinstance(text, str) and text:
                chunks.append(text)
    return "\n".join(chunks).strip()
