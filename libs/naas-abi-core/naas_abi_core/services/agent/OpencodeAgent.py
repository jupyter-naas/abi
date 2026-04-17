from __future__ import annotations

import asyncio
import atexit
import contextlib
import json
import os
import random
import shlex
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock, Thread
from typing import Any, AsyncIterator, Optional

import httpx
from fastapi import APIRouter
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.services.agent.OpencodeSessionService import OpencodeSessionService
from naas_abi_core.utils.Expose import Expose
from naas_abi_core.utils.Logger import logger
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse


class OpencodeError(Exception):
    """Base exception for OpencodeAgent errors."""


class OpencodeUnavailableError(OpencodeError):
    """Server could not be reached (connection refused, timeout)."""


class OpencodeRequestError(OpencodeError):
    """Server returned a non-2xx response."""

    def __init__(self, status_code: int, body: str):
        super().__init__(f"opencode request failed ({status_code}): {body}")
        self.status_code = status_code
        self.body = body


class OpencodeStartupError(OpencodeError):
    """Server process failed to become ready within startup_timeout."""


class OpencodeTimeoutError(OpencodeError):
    """A request to the opencode server timed out."""


@dataclass
class OpencodeAgentConfiguration:
    workdir: str
    port: int | None
    name: str
    description: str
    model: str | None = None
    system_prompt: str = ""
    opencode_bin: str = "opencode"
    startup_timeout: int = 15
    request_timeout: float | None = None


class OpencodeCompletionQuery(BaseModel):
    prompt: str = Field(..., description="The prompt to send to the opencode agent")
    thread_id: str = Field(default="", description="Optional conversation thread id")


class OpencodeToolInput(BaseModel):
    message: str = Field(
        description="The development task to perform. Be specific about expected output."
    )
    thread_id: str = Field(
        default="",
        description="Opencode session ID to continue an existing conversation. Leave empty to start fresh.",
    )


class OpencodeAgent(Expose):
    _auth_bootstrap_done: bool = False
    _auth_bootstrap_lock: Lock = Lock()

    def __init__(
        self,
        configuration: OpencodeAgentConfiguration,
        agent_shared_state: Any | None = None,
        session_service: OpencodeSessionService | None = None,
    ):
        self.conf = configuration
        if agent_shared_state is None:
            from naas_abi_core.services.agent.Agent import AgentSharedState

            agent_shared_state = AgentSharedState()
        self.state = agent_shared_state
        self.session_service = session_service
        self._proc: subprocess.Popen[str] | None = None
        self._primed_sessions: set[str] = set()
        self._thread_to_session: dict[str, str] = {}
        self._on_tool_usage = lambda _: None
        self._on_tool_response = lambda _: None
        self._on_ai_message = lambda _message, _agent_name: None
        self._approved_permissions: set[str] = set()
        self._seen_tool_calls: set[str] = set()

        atexit.register(self.stop)

    @property
    def name(self) -> str:
        return self.conf.name

    @property
    def description(self) -> str:
        return self.conf.description

    @property
    def agents(self) -> list[Any]:
        return []

    @property
    def chat_model(self) -> Any | None:
        return None

    @property
    def _base_url(self) -> str:
        if self.conf.port is None:
            raise OpencodeStartupError("opencode port is not initialized")
        return f"http://127.0.0.1:{self.conf.port}"

    @property
    def _health_url(self) -> str:
        return f"{self._base_url}/global/health"

    def start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return

        self._ensure_opencode_auth_file_once()

        self._ensure_port()

        if self.conf.port is None:
            raise OpencodeStartupError("opencode port is not initialized")

        if not self._is_port_available(self.conf.port):
            try:
                response = httpx.get(self._health_url, timeout=1.0)
                if self._is_healthy(response):
                    return
            except Exception:
                pass
            raise OpencodeStartupError(
                f"opencode port {self.conf.port} is already in use"
            )

        try:
            response = httpx.get(self._health_url, timeout=1.0)
            if self._is_healthy(response):
                return
        except Exception:
            pass

        os.makedirs(self.conf.workdir, exist_ok=True)

        launch_command = (
            f"source ~/.bashrc >/dev/null 2>&1; "
            f"{shlex.quote(self.conf.opencode_bin)} serve --port {self.conf.port}"
        )

        self._proc = subprocess.Popen(
            ["bash", "-lc", launch_command],
            cwd=self.conf.workdir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self._wait_ready()

    @classmethod
    def _ensure_opencode_auth_file_once(cls) -> None:
        with cls._auth_bootstrap_lock:
            if cls._auth_bootstrap_done:
                return

            try:
                cls._ensure_opencode_auth_file()
                cls._auth_bootstrap_done = True
            except Exception as e:
                logger.warning(f"Failed to initialize opencode auth file: {e}")

    @classmethod
    def _ensure_opencode_auth_file(cls) -> None:
        from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
            EngineConfiguration,
        )

        configuration = EngineConfiguration.load_configuration()
        opencode_configuration = getattr(configuration, "opencode", None)
        if opencode_configuration is None:
            return

        providers = getattr(opencode_configuration, "providers", []) or []
        if len(providers) == 0:
            return

        auth_file_path = Path(
            os.path.expanduser(
                str(
                    getattr(
                        opencode_configuration,
                        "auth_file_path",
                        "~/.local/share/opencode/auth.json",
                    )
                )
            )
        )
        auth_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Only bootstrap the file if it does not already exist.
        # We should not mutate existing local credentials.
        if auth_file_path.exists():
            return

        auth_data: dict[str, Any] = {}
        for provider in providers:
            provider_id = str(getattr(provider, "id", "")).strip()
            provider_key = str(getattr(provider, "key", "")).strip()
            if not provider_id or not provider_key:
                continue

            record: dict[str, Any] = {
                "type": "api",
                "key": provider_key,
            }
            metadata = getattr(provider, "metadata", None)
            if isinstance(metadata, dict) and metadata:
                record["metadata"] = {
                    str(k): str(v)
                    for k, v in metadata.items()
                    if isinstance(k, str) and isinstance(v, str)
                }

            auth_data[provider_id] = record

        if len(auth_data) == 0:
            return

        auth_file_path.write_text(
            json.dumps(auth_data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.chmod(auth_file_path, 0o600)
        logger.debug(f"Initialized opencode auth file at {auth_file_path}")

    @staticmethod
    def _model_payload(model: str | None) -> dict[str, str] | None:
        if not model:
            return None
        model_value = model.strip()
        if not model_value or "/" not in model_value:
            return None
        provider_id, model_id = model_value.split("/", 1)
        provider_id = provider_id.strip()
        model_id = model_id.strip()
        if not provider_id or not model_id:
            return None
        return {"providerID": provider_id, "modelID": model_id}

    def _wait_ready(self) -> None:
        deadline = time.monotonic() + self.conf.startup_timeout
        last_error: Exception | None = None

        while time.monotonic() < deadline:
            if self._proc is not None and self._proc.poll() is not None:
                raise OpencodeStartupError("opencode server exited during startup")

            try:
                response = httpx.get(self._health_url, timeout=1.0)
                if self._is_healthy(response):
                    return
            except Exception as e:
                last_error = e

            time.sleep(0.25)

        raise OpencodeStartupError(
            f"opencode server did not become ready within {self.conf.startup_timeout}s"
            + (f": {last_error}" if last_error else "")
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

    def _ensure_port(self) -> None:
        if self.conf.port is not None:
            return

        self.conf.port = self._find_available_port()
        logger.debug(f"Assigned dynamic opencode port: {self.conf.port}")

    @staticmethod
    def _is_port_available(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False

    def _find_available_port(self) -> int:
        for _ in range(200):
            candidate = random.randint(4096, 4199)
            if self._is_port_available(candidate):
                return candidate

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            assigned = sock.getsockname()[1]
            return int(assigned)

    def duplicate(
        self, queue: Any | None = None, agent_shared_state: Any | None = None
    ):
        del queue
        return self.__class__(
            configuration=self.conf,
            agent_shared_state=agent_shared_state or self.state,
            session_service=self.session_service,
        )

    def on_tool_usage(self, callback):
        self._on_tool_usage = callback

    def on_tool_response(self, callback):
        self._on_tool_response = callback

    def on_ai_message(self, callback):
        self._on_ai_message = callback

    def reset(self) -> None:
        if hasattr(self.state, "set_thread_id") and hasattr(self.state, "thread_id"):
            try:
                current_thread_id = int(self.state.thread_id)
                self.state.set_thread_id(str(current_thread_id + 1))
                return
            except Exception:
                pass
        self._thread_to_session = {}

    def invoke(self, prompt: str, thread_id: Optional[str] = None) -> str:
        return _run_coroutine_sync(self.ainvoke(message=prompt, thread_id=thread_id))

    async def ainvoke(self, message: str, thread_id: Optional[str] = None) -> str:
        self.start()

        try:
            async with httpx.AsyncClient(timeout=self._http_timeout()) as client:
                session_id = await self._get_or_create_session(client, thread_id)
                await self._ensure_system_prompt(client, session_id)
                stop_events = asyncio.Event()
                event_task = asyncio.create_task(
                    self._watch_session_events(client, session_id, stop_events)
                )
                try:
                    payload = await self._prompt(client, session_id, message)
                finally:
                    stop_events.set()
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(event_task, timeout=1.0)
                parts = self._extract_parts(payload)
                completion = self._extract_text(parts)
                await self._persist_best_effort(
                    session_id=session_id,
                    thread_id=thread_id,
                    user_message=message,
                    assistant_parts=parts,
                )
                self._on_ai_message(AIMessage(content=completion), self.conf.name)
                return completion
        except httpx.ReadTimeout as e:
            raise OpencodeTimeoutError(
                "opencode request timed out. "
                "For long-running tasks or permission-gated runs, use streaming "
                "or increase OpencodeAgentConfiguration.request_timeout."
            ) from e
        except httpx.ConnectError as e:
            raise OpencodeUnavailableError(str(e)) from e

    async def _watch_session_events(
        self,
        client: httpx.AsyncClient,
        session_id: str,
        stop_events: asyncio.Event,
    ) -> None:
        try:
            async with client.stream("GET", f"{self._base_url}/event") as response:
                if response.status_code >= 300:
                    return

                async for line in response.aiter_lines():
                    if stop_events.is_set():
                        return
                    if not line.startswith("data:"):
                        continue

                    data = line.removeprefix("data:").strip()
                    if not data:
                        continue

                    try:
                        event = json.loads(data)
                    except Exception:
                        continue

                    properties = event.get("properties") or {}
                    event_session = properties.get("sessionID")
                    if event_session and event_session != session_id:
                        continue

                    await self._handle_event(client, session_id, event)
        except Exception:
            return

    async def _handle_event(
        self,
        client: httpx.AsyncClient,
        session_id: str,
        event: dict[str, Any],
    ) -> None:
        event_type = str(event.get("type") or "")
        properties = event.get("properties") or {}

        for permission_id in self._collect_permission_ids(event):
            if permission_id in self._approved_permissions:
                continue
            if await self._auto_approve_permission(client, session_id, permission_id):
                self._approved_permissions.add(permission_id)
                self._notify_tool_response(
                    ToolMessage(
                        content=(f"Auto-approved opencode permission `{permission_id}`")
                    )
                )

        if "question" in event_type.lower():
            question_payload = properties.get("question") or properties
            options = (
                question_payload.get("options")
                if isinstance(question_payload, dict)
                else None
            )
            question_text = (
                question_payload.get("question")
                if isinstance(question_payload, dict)
                else None
            )
            if isinstance(options, list):
                rendered_options = "\n".join(
                    [f"- {opt}" for opt in options if isinstance(opt, str)]
                )
                content = (
                    f"Selection requested by opencode:\n{question_text or ''}\n{rendered_options}"
                ).strip()
                self._notify_tool_response(ToolMessage(content=content))

        if event_type != "message.part.updated":
            return

        part = properties.get("part") or {}
        if not isinstance(part, dict):
            return

        part_type = part.get("type")
        if part_type == "reasoning":
            self._notify_tool_usage(ToolMessage(content="Model is reasoning..."))
            return

        if part_type != "tool":
            return

        tool_name = str(part.get("tool") or "tool")
        state = part.get("state") or {}
        if not isinstance(state, dict):
            return

        status = str(state.get("status") or "")
        call_id = str(part.get("callID") or "")
        if status in {"pending", "running"}:
            dedupe = call_id or f"{tool_name}:{status}"
            if dedupe not in self._seen_tool_calls:
                self._seen_tool_calls.add(dedupe)
                self._notify_tool_usage(ToolMessage(content=f"{tool_name} ({status})"))
            return

        if status == "completed":
            output = state.get("output")
            if isinstance(output, str) and output:
                self._notify_tool_response(ToolMessage(content=output))

    async def _auto_approve_permission(
        self,
        client: httpx.AsyncClient,
        session_id: str,
        permission_id: str,
    ) -> bool:
        payloads = [{"response": "always"}, {"response": "once"}]
        for payload in payloads:
            try:
                response = await client.post(
                    f"{self._base_url}/session/{session_id}/permissions/{permission_id}",
                    json=payload,
                )
                if response.status_code < 300:
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _collect_permission_ids(event: dict[str, Any]) -> set[str]:
        found: set[str] = set()

        def _walk(value: Any) -> None:
            if isinstance(value, dict):
                for item in value.values():
                    _walk(item)
                return
            if isinstance(value, list):
                for item in value:
                    _walk(item)
                return
            if isinstance(value, str) and value.startswith("per_"):
                found.add(value)

        _walk(event)
        return found

    async def astream(
        self,
        message: str,
        thread_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        self.start()

        try:
            async with httpx.AsyncClient(timeout=self._http_timeout()) as client:
                session_id = await self._get_or_create_session(client, thread_id)
                await self._ensure_system_prompt(client, session_id)

                prompt_task = asyncio.create_task(
                    self._prompt(client, session_id, message)
                )

                async with client.stream("GET", f"{self._base_url}/event") as response:
                    if response.status_code >= 300:
                        body = await response.aread()
                        raise OpencodeRequestError(response.status_code, body.decode())

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
                        event_session_id = properties.get("sessionID")
                        if event_session_id and event_session_id != session_id:
                            continue

                        await self._handle_event(client, session_id, event)
                        yield data

                        if (
                            event.get("type") == "session.idle"
                            and properties.get("sessionID") == session_id
                            and prompt_task.done()
                        ):
                            break

                payload = await prompt_task
                parts = self._extract_parts(payload)

                await self._persist_best_effort(
                    session_id=session_id,
                    thread_id=thread_id,
                    user_message=message,
                    assistant_parts=parts,
                )
        except httpx.ReadTimeout as e:
            raise OpencodeTimeoutError(
                "opencode streaming request timed out. "
                "Increase OpencodeAgentConfiguration.request_timeout "
                "or keep it unset for no read timeout."
            ) from e
        except httpx.ConnectError as e:
            raise OpencodeUnavailableError(str(e)) from e

    def _http_timeout(self) -> httpx.Timeout:
        if self.conf.request_timeout is None:
            return httpx.Timeout(connect=10.0, write=60.0, read=None, pool=60.0)
        return httpx.Timeout(self.conf.request_timeout)

    async def stream(
        self,
        message: str,
        thread_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        async for chunk in self.astream(message=message, thread_id=thread_id):
            yield chunk

    async def _get_or_create_session(
        self,
        client: httpx.AsyncClient,
        thread_id: Optional[str],
    ) -> str:
        if thread_id:
            cached = self._thread_to_session.get(thread_id)
            if cached:
                return cached

            response = await client.get(f"{self._base_url}/session/{thread_id}")
            if response.status_code == 200:
                self._thread_to_session[thread_id] = thread_id
                return thread_id

        title = f"{self.conf.name}-{datetime.now(timezone.utc).isoformat()}"
        response = await client.post(f"{self._base_url}/session", json={"title": title})
        self._raise_for_status(response)

        payload = response.json()
        session_id = (
            payload.get("id")
            or payload.get("session", {}).get("id")
            or payload.get("session_id")
        )
        if not session_id:
            raise OpencodeRequestError(response.status_code, response.text)

        if thread_id:
            self._thread_to_session[thread_id] = session_id

        return str(session_id)

    async def _ensure_system_prompt(
        self, client: httpx.AsyncClient, session_id: str
    ) -> None:
        if not self.conf.system_prompt:
            return
        if session_id in self._primed_sessions:
            return

        await self._prompt(client, session_id, self.conf.system_prompt, no_reply=True)
        self._primed_sessions.add(session_id)

    async def _prompt(
        self,
        client: httpx.AsyncClient,
        session_id: str,
        message: str,
        no_reply: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "parts": [{"type": "text", "text": message}],
            "noReply": no_reply,
        }
        model_payload = self._model_payload(self.conf.model)
        if model_payload is not None:
            payload["model"] = model_payload

        response = await client.post(
            f"{self._base_url}/session/{session_id}/message",
            json=payload,
        )
        self._raise_for_status(response)
        response_text = response.text.strip()
        if not response_text:
            return {"parts": []}

        try:
            payload = response.json()
            if isinstance(payload, dict):
                return payload
        except ValueError:
            if no_reply:
                return {"parts": []}
            return {"parts": [{"type": "text", "text": response_text}]}

        return {"parts": []}

    @staticmethod
    def _is_healthy(response: httpx.Response) -> bool:
        if response.status_code != 200:
            return False
        try:
            payload = response.json()
        except Exception:
            return False
        return isinstance(payload, dict) and payload.get("healthy") is True

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 300:
            raise OpencodeRequestError(response.status_code, response.text)

    @staticmethod
    def _extract_parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
        parts = payload.get("parts")
        if isinstance(parts, list):
            return [part for part in parts if isinstance(part, dict)]

        message = payload.get("message")
        if isinstance(message, dict) and isinstance(message.get("parts"), list):
            return [part for part in message["parts"] if isinstance(part, dict)]

        return []

    @staticmethod
    def _extract_text(parts: list[dict[str, Any]]) -> str:
        chunks: list[str] = []
        for part in parts:
            text = part.get("text") or part.get("content")
            if isinstance(text, str):
                chunks.append(text)
        return "\n".join([chunk for chunk in chunks if chunk]).strip()

    @staticmethod
    def _extract_stream_text(data: str) -> str:
        try:
            payload = json.loads(data)
            content = payload.get("content")
            if isinstance(content, str):
                return content
        except Exception:
            return ""
        return ""

    async def _persist_best_effort(
        self,
        session_id: str,
        thread_id: Optional[str],
        user_message: str,
        assistant_parts: list[dict[str, Any]],
    ) -> None:
        if self.session_service is None:
            return

        try:
            session = await self.session_service.get_or_create_session(
                opencode_id=session_id,
                agent_name=self.conf.name,
                workdir=os.path.abspath(self.conf.workdir),
                abi_thread_id=thread_id,
                title=None,
            )

            user_parts = [{"type": "text", "text": user_message}]
            await self.session_service.persist_message(session, "user", user_parts)
            assistant_message = await self.session_service.persist_message(
                session, "assistant", assistant_parts
            )
            await self.session_service.persist_file_events(
                assistant_message, assistant_parts
            )
        except Exception as e:
            logger.error(f"Opencode persistence failed: {e}")

    def as_tools(self) -> list[BaseTool]:
        async def _tool_async(message: str, thread_id: str = "") -> str:
            return await self.ainvoke(message=message, thread_id=thread_id or None)

        def _tool_sync(message: str, thread_id: str = "") -> str:
            return self.invoke(prompt=message, thread_id=thread_id or None)

        tool = StructuredTool.from_function(
            func=_tool_sync,
            coroutine=_tool_async,
            name=self.conf.name,
            description=self.conf.description,
            args_schema=OpencodeToolInput,
        )
        return [tool]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        route_name = route_name or self.conf.name
        name = name or self.conf.name.capitalize().replace("_", " ")
        description = description or self.conf.description
        description_stream = description_stream or self.conf.description

        @router.post(
            f"/{route_name}/completion" if route_name else "/completion",
            name=f"{name} completion",
            description=description,
            tags=tags,
        )
        async def completion(query: OpencodeCompletionQuery):
            completion_text = await self.ainvoke(
                message=query.prompt,
                thread_id=query.thread_id or None,
            )
            return {"completion": completion_text}

        @router.post(
            f"/{route_name}/stream-completion" if route_name else "/stream-completion",
            name=f"{name} stream completion",
            description=description_stream,
            tags=tags,
        )
        async def stream_completion(query: OpencodeCompletionQuery):
            async def _events() -> AsyncIterator[dict[str, str]]:
                async for chunk in self.stream(
                    message=query.prompt,
                    thread_id=query.thread_id or None,
                ):
                    yield {"data": chunk}

                yield {
                    "data": json.dumps(
                        {
                            "type": "end",
                            "metadata": {"thread_id": query.thread_id or ""},
                        }
                    )
                }

            return EventSourceResponse(
                _events(),
                media_type="text/event-stream; charset=utf-8",
            )

    def _notify_tool_usage(self, message: AnyMessage) -> None:
        self._on_tool_usage(message)

    def _notify_tool_response(self, message: AnyMessage) -> None:
        self._on_tool_response(message)

    def _notify_ai_message(self, message: AnyMessage, agent_name: str) -> None:
        self._on_ai_message(message, agent_name)


def _run_coroutine_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    container: dict[str, Any] = {}

    def _runner() -> None:
        try:
            container["result"] = asyncio.run(coro)
        except Exception as e:
            container["error"] = e

    thread = Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if "error" in container:
        raise container["error"]

    return container.get("result")
