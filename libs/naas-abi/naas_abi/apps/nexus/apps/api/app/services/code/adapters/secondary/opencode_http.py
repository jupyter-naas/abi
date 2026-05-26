from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from collections.abc import AsyncIterator

import httpx
from naas_abi.apps.nexus.apps.api.app.services.code.code__schema import (
    CodeOpencodeChatInput,
    CodeOpencodeUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.code.port import CodeOpencodePort

_resolved_opencode_base: str | None = None


class OpencodeHttpAdapter(CodeOpencodePort):
    def __init__(self) -> None:
        self._agent = None
        self._agent_lock = asyncio.Lock()
        self._workdir_override: str | None = None

    def set_workdir(self, path: str) -> None:
        self._workdir_override = path
        agent = self._agent
        if agent is not None and getattr(agent, "conf", None) is not None:
            agent.conf.workdir = path

    def _effective_workdir(self) -> str:
        if self._workdir_override:
            return self._workdir_override
        return os.environ.get("OPENCODE_WORKDIR") or os.environ.get("FILESYSTEM_ROOT", "/app")

    def _get_agent(self):
        if self._agent is not None:
            return self._agent

        from threading import Lock

        lock = Lock()
        with lock:
            if self._agent is not None:
                return self._agent

            from naas_abi_core.services.agent.OpencodeAgent import (
                OpencodeAgent,
                OpencodeAgentConfiguration,
            )

            port = None
            workdir = self._effective_workdir()
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

            self._agent = OpencodeAgent(
                configuration=OpencodeAgentConfiguration(
                    workdir=workdir,
                    port=port,
                    host=host,
                    name="opencode",
                    description="AI coding assistant",
                    model=str(model) if model else None,
                )
            )
        return self._agent

    def _base_url(self) -> str:
        return self._get_agent()._base_url

    def get_agent_port(self) -> int:
        return self._get_agent().conf.port

    def _opencode_base_candidates(self) -> list[str]:
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

    def _sync_agent_from_base(self, base: str) -> None:
        from urllib.parse import urlparse

        agent = self._get_agent()
        parsed = urlparse(base)
        conf = getattr(agent, "conf", None)
        if conf is None:
            return
        conf.host = parsed.hostname or "127.0.0.1"
        conf.port = parsed.port or int(os.environ.get("OPENCODE_PORT", "4005"))

    async def resolve_base_url(self) -> str:
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
        for base in self._opencode_base_candidates():
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(f"{base}/global/health")
                    if response.status_code == 200 and response.json().get("healthy") is True:
                        _resolved_opencode_base = base
                        self._sync_agent_from_base(base)
                        return base
            except Exception as exc:
                last_error = str(exc)

        raise CodeOpencodeUnavailableError(
            "opencode is not running. On your Mac, run: make opencode-up "
            f"(checked: {', '.join(self._opencode_base_candidates())}"
            + (f"; {last_error}" if last_error else "")
            + ")"
        )

    async def health(self) -> dict[str, object]:
        try:
            base = await self.resolve_base_url()
            agent = self._get_agent()
            return {"healthy": True, "port": agent.conf.port, "baseUrl": base}
        except CodeOpencodeUnavailableError as exc:
            return {"healthy": False, "error": str(exc)}
        except Exception as exc:
            return {"healthy": False, "error": str(exc)}

    async def proxy_get(self, path: str) -> object:
        base = await self.resolve_base_url()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base}/{path}")
            if response.status_code >= 300:
                raise httpx.HTTPStatusError(
                    response.text,
                    request=response.request,
                    response=response,
                )
            return response.json()

    async def proxy_post(self, path: str, body: dict | None = None) -> object:
        base = await self.resolve_base_url()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{base}/{path}", json=body or {})
            if response.status_code >= 300:
                raise httpx.HTTPStatusError(
                    response.text,
                    request=response.request,
                    response=response,
                )
            return response.json()

    async def proxy_delete(self, path: str) -> object:
        base = await self.resolve_base_url()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.delete(f"{base}/{path}")
            if response.status_code >= 300:
                raise httpx.HTTPStatusError(
                    response.text,
                    request=response.request,
                    response=response,
                )
            return response.json()

    def _ensure_session_dir(self, session_id: str) -> str:
        workdir = self._effective_workdir()
        os.makedirs(workdir, exist_ok=True)
        return workdir

    def _build_skills_note(self) -> str:
        skills_dir = os.path.join(self._effective_workdir(), "skills")
        if not os.path.isdir(skills_dir):
            return ""

        skill_files = [
            f
            for f in os.listdir(skills_dir)
            if f.endswith((".py", ".sh", ".ts", ".js")) and not f.startswith("_")
        ]
        if not skill_files:
            return ""

        skill_entries: list[str] = []
        for fname in sorted(skill_files):
            fpath = os.path.join(skills_dir, fname)
            description = ""
            try:
                with open(fpath, encoding="utf-8", errors="ignore") as skill_file:
                    in_docstring = False
                    for line in skill_file:
                        stripped = line.strip()
                        if not in_docstring:
                            if stripped.startswith('"""') or stripped.startswith("'''"):
                                inner = stripped.strip("\"' ")
                                if inner:
                                    description = inner.rstrip('"\'').strip()
                                    break
                                in_docstring = True
                            elif (
                                stripped
                                and not stripped.startswith("#!")
                                and not stripped.startswith("#")
                            ):
                                break
                        else:
                            if (
                                stripped
                                and not stripped.startswith('"""')
                                and not stripped.startswith("'''")
                            ):
                                description = stripped
                            break
            except OSError:
                pass
            entry = fname if not description else f"{fname} ({description})"
            skill_entries.append(entry)

        return (
            "\n[Skills in code/skills/ — invoke with bash when the user's request matches: "
            + "; ".join(skill_entries)
            + "]"
        )

    async def stream_chat(self, input_data: object) -> AsyncIterator[str]:
        if not isinstance(input_data, CodeOpencodeChatInput):
            raise TypeError("input_data must be CodeOpencodeChatInput")

        agent = self._get_agent()
        loop = asyncio.get_running_loop()
        session_id = input_data.session_id or "default"
        session_dir = self._ensure_session_dir(session_id)
        skills_note = self._build_skills_note()
        message_with_ctx = (
            f"[Session working directory: {session_dir}]{skills_note}\n\n"
            f"{input_data.message}"
        )

        if input_data.model_provider_id and input_data.model_id:
            async for event in self._stream_with_model(
                agent=agent,
                loop=loop,
                session_id=session_id,
                message_with_ctx=message_with_ctx,
                model_provider_id=input_data.model_provider_id,
                model_id=input_data.model_id,
                oc_agent=input_data.agent or None,
            ):
                yield event
            return

        try:
            await loop.run_in_executor(None, agent.start)
            oc_agent = input_data.agent or None
            async for raw_event in agent.astream(
                message=message_with_ctx,
                thread_id=session_id,
                agent=oc_agent,
            ):
                yield raw_event
        except Exception as exc:
            yield json.dumps({"type": "error", "message": str(exc)})
        finally:
            yield json.dumps({"type": "done"})

    async def _stream_with_model(
        self,
        agent: object,
        loop: asyncio.AbstractEventLoop,
        session_id: str,
        message_with_ctx: str,
        model_provider_id: str,
        model_id: str,
        oc_agent: str | None,
    ) -> AsyncIterator[str]:
        import contextlib

        try:
            await loop.run_in_executor(None, agent.start)
            base = self._base_url()

            async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=5.0)) as client:
                sess_r = await client.get(f"{base}/session/{session_id}")
                if sess_r.status_code == 200:
                    oc_session_id = sess_r.json().get("id", session_id)
                else:
                    cr = await client.post(
                        f"{base}/session",
                        json={"title": f"nexus-{session_id}"},
                    )
                    cr.raise_for_status()
                    oc_session_id = cr.json().get("id", session_id)

                prompt_payload: dict = {
                    "parts": [{"type": "text", "text": message_with_ctx}],
                    "model": {"providerID": model_provider_id, "modelID": model_id},
                }
                if oc_agent:
                    prompt_payload["agent"] = oc_agent
                prompt_task = asyncio.create_task(
                    client.post(f"{base}/session/{oc_session_id}/message", json=prompt_payload)
                )

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
                        yield raw
                        if (
                            ev.get("type") == "session.idle"
                            and props.get("sessionID") == oc_session_id
                        ):
                            if not prompt_task.done():
                                with contextlib.suppress(Exception):
                                    await asyncio.wait_for(
                                        asyncio.shield(prompt_task),
                                        timeout=3.0,
                                    )
                            break
        except Exception as exc:
            yield json.dumps({"type": "error", "message": str(exc)})
        finally:
            yield json.dumps({"type": "done"})


def parse_model_ref(model_value: str | None) -> tuple[str, str] | None:
    if not model_value or "/" not in model_value:
        return None
    provider_id, model_id = model_value.strip().split("/", 1)
    provider_id = provider_id.strip()
    model_id = model_id.strip()
    if provider_id and model_id:
        return provider_id, model_id
    return None


def lookup_model_name(providers_data: object, provider_id: str, model_id: str) -> str:
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


def first_available_model(providers_data: object) -> tuple[str, str, str] | None:
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
                model_id = str(
                    model.get("modelID") or model.get("modelId") or model.get("id") or ""
                )
                if model_id:
                    name = str(model.get("name") or model_id)
                    return provider_id, model_id, name
    return None


class BroadcastLogsAdapter:
    _buffer_size = 500

    def __init__(self) -> None:
        self._log_buffer: deque[str] = deque(maxlen=self._buffer_size)
        self._listeners: list[asyncio.Queue[str]] = []
        self._handler = self._build_handler()
        logging.getLogger().addHandler(self._handler)

    def _build_handler(self) -> logging.Handler:
        adapter = self

        class BroadcastHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                try:
                    line = self.format(record)
                except Exception:
                    return
                adapter._log_buffer.append(line)
                for queue in list(adapter._listeners):
                    try:
                        queue.put_nowait(line)
                    except asyncio.QueueFull:
                        pass

        handler = BroadcastHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        handler.setLevel(logging.DEBUG)
        return handler

    def get_recent_lines(self) -> list[str]:
        return list(self._log_buffer)

    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
        self._listeners.append(queue)
        return queue

    def unsubscribe(self, listener: object) -> None:
        if isinstance(listener, asyncio.Queue):
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass


_logs_adapter: BroadcastLogsAdapter | None = None


def get_broadcast_logs_adapter() -> BroadcastLogsAdapter:
    global _logs_adapter
    if _logs_adapter is None:
        _logs_adapter = BroadcastLogsAdapter()
    return _logs_adapter
