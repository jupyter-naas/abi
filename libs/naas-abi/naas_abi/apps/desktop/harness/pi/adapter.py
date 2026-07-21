"""pi harness adapter (Mario Zechner's pi-mono coding agent).

Integrates against pi's RPC mode (``pi --mode rpc``): strict LF-delimited
JSONL over stdin/stdout. Commands go to stdin; command responses
(``type: "response"``) and agent events stream back on stdout.

Protocol reference: pi-mono ``packages/coding-agent/docs/rpc.md``.

Design and assumptions:

- One pi RPC process per desktop session (pi is single-session per
  process; ``create_session`` spawns, ``delete_session`` terminates).
- A session id that has no live process (e.g. after an app restart) is
  transparently re-attached to a fresh pi process; pi-side history is
  not restored, the desktop store owns chat history.
- Models are selected per prompt via the ``set_model`` command using the
  desktop's ``provider/model_id`` convention; ``get_available_models``
  feeds ``list_models`` (grouped by provider).
- The ``agent`` parameter (opencode's plan/build concept) has no pi
  equivalent and is ignored.
- Streamed ``text_delta`` events are accumulated so ``TextEvent`` stays
  cumulative per part, matching the legacy opencode wire contract.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from typing import Any, AsyncIterator, Awaitable, Callable, Protocol

from ..models import (
    DoneEvent,
    ErrorEvent,
    HarnessEvent,
    HarnessModel,
    HarnessProvider,
    ReasoningEvent,
    TextEvent,
    ToolEvent,
)
from ..port import HarnessError, HarnessPort, HarnessUnavailableError

_COMMAND_TIMEOUT = 30.0


class PiProcess(Protocol):
    """Subset of ``asyncio.subprocess.Process`` the adapter relies on."""

    stdin: Any  # write(bytes) + drain()
    stdout: Any  # readline() -> bytes
    returncode: int | None

    def terminate(self) -> None: ...

    async def wait(self) -> int: ...


ProcessFactory = Callable[[list[str], str], Awaitable[PiProcess]]


async def _spawn_pi(args: list[str], cwd: str) -> PiProcess:
    return await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )


class PiHarnessAdapter(HarnessPort):
    """Adapter over per-session ``pi --mode rpc`` subprocesses."""

    def __init__(
        self,
        workspace_root: str,
        pi_bin: str = "pi",
        process_factory: ProcessFactory | None = None,
        which: Callable[[str], str | None] = shutil.which,
    ):
        self.workspace_root = workspace_root
        self.pi_bin = pi_bin
        self._process_factory = process_factory or _spawn_pi
        self._which = which
        self._sessions: dict[str, PiProcess] = {}

    # -- lifecycle ------------------------------------------------------

    async def start(self) -> None:
        if self._which(self.pi_bin) is None:
            raise HarnessUnavailableError(
                f"pi binary not found on PATH (looked for {self.pi_bin!r}); "
                "install it with: npm install -g @earendil-works/pi-coding-agent"
            )

    async def stop(self) -> None:
        sessions, self._sessions = self._sessions, {}
        for proc in sessions.values():
            await _terminate(proc)

    async def restart(
        self, workspace_root: str | None = None, binary: str | None = None
    ) -> None:
        await self.stop()
        if workspace_root:
            self.workspace_root = workspace_root
        if binary:
            self.pi_bin = binary
        await self.start()

    async def health(self) -> bool:
        return self._which(self.pi_bin) is not None

    # -- models -----------------------------------------------------------

    async def list_models(self) -> list[HarnessProvider]:
        proc = await self._spawn(title="", workspace_root=self.workspace_root)
        try:
            response = await self._command(proc, {"type": "get_available_models"})
            models = (response.get("data") or {}).get("models") or []
        finally:
            await _terminate(proc)

        by_provider: dict[str, list[HarnessModel]] = {}
        for model in models:
            if not isinstance(model, dict) or not model.get("id"):
                continue
            provider = str(model.get("provider") or "unknown")
            by_provider.setdefault(provider, []).append(
                HarnessModel(
                    id=str(model["id"]), name=str(model.get("name") or model["id"])
                )
            )
        return [
            HarnessProvider(id=provider, name=provider, models=tuple(models))
            for provider, models in sorted(by_provider.items())
        ]

    # -- sessions -----------------------------------------------------------

    async def create_session(
        self, title: str = "", workspace_root: str | None = None
    ) -> str:
        session_id = f"pi_{uuid.uuid4().hex}"
        self._sessions[session_id] = await self._spawn(
            title=title, workspace_root=workspace_root or self.workspace_root
        )
        return session_id

    async def delete_session(self, session_id: str) -> None:
        proc = self._sessions.pop(session_id, None)
        if proc is not None:
            await _terminate(proc)

    async def abort(self, session_id: str) -> None:
        proc = self._sessions.get(session_id)
        if proc is None or proc.returncode is not None:
            return
        await _send(proc, {"type": "abort"})

    # -- prompting ------------------------------------------------------------

    async def stream_prompt(
        self,
        session_id: str,
        text: str,
        model: str | None = None,
        agent: str | None = None,
    ) -> AsyncIterator[HarnessEvent]:
        # ``agent`` (opencode plan/build) has no pi equivalent; ignored.
        proc = await self._ensure_session(session_id)

        if model and "/" in model:
            provider, model_id = model.split("/", 1)
            await _send(
                proc,
                {
                    "type": "set_model",
                    "provider": provider.strip(),
                    "modelId": model_id.strip(),
                    "id": "set-model",
                },
            )

        await _send(proc, {"type": "prompt", "message": text, "id": "prompt"})

        texts: dict[str, str] = {}  # part_id -> accumulated text
        last_part_id = ""
        final_text = ""
        reasoning_parts: set[str] = set()

        while True:
            line = await proc.stdout.readline()
            if not line:
                yield ErrorEvent(message="pi process exited unexpectedly")
                self._sessions.pop(session_id, None)
                yield DoneEvent(text=final_text or texts.get(last_part_id, ""))
                return

            event = _parse_line(line)
            if event is None:
                continue
            event_type = event.get("type")

            if event_type == "response":
                if event.get("success") is False:
                    message = str(event.get("error") or "pi command failed")
                    yield ErrorEvent(message=message)
                    if event.get("id") == "prompt" or event.get("command") == "prompt":
                        yield DoneEvent(text="")
                        return
                continue

            if event_type == "message_update":
                delta = event.get("assistantMessageEvent") or {}
                delta_type = delta.get("type")
                part_id = f"part-{delta.get('contentIndex', 0)}"
                if delta_type == "text_delta":
                    texts[part_id] = texts.get(part_id, "") + str(
                        delta.get("delta") or ""
                    )
                    last_part_id = part_id
                    yield TextEvent(text=texts[part_id], part_id=part_id)
                elif delta_type in ("thinking_start", "thinking_delta"):
                    if part_id not in reasoning_parts:
                        reasoning_parts.add(part_id)
                        yield ReasoningEvent()
                elif delta_type == "error":
                    yield ErrorEvent(
                        message=str(delta.get("reason") or "pi stream error")
                    )
                continue

            if event_type == "tool_execution_start":
                args = event.get("args") if isinstance(event.get("args"), dict) else {}
                yield ToolEvent(
                    call_id=str(event.get("toolCallId") or ""),
                    name=str(event.get("toolName") or "tool"),
                    status="running",
                    title=_tool_title(args),
                    input=args or None,
                )
                continue

            if event_type == "tool_execution_update":
                partial = event.get("partialResult") or {}
                yield ToolEvent(
                    call_id=str(event.get("toolCallId") or ""),
                    name=str(event.get("toolName") or "tool"),
                    status="running",
                    title=_tool_title(
                        event.get("args") if isinstance(event.get("args"), dict) else {}
                    ),
                    output=_content_text(partial.get("content")) or None,
                )
                continue

            if event_type == "tool_execution_end":
                result = event.get("result") or {}
                yield ToolEvent(
                    call_id=str(event.get("toolCallId") or ""),
                    name=str(event.get("toolName") or "tool"),
                    status="error" if event.get("isError") else "completed",
                    output=_content_text(result.get("content")) or None,
                )
                continue

            if event_type == "agent_end":
                final_text = _last_assistant_text(event.get("messages"))
                yield DoneEvent(text=final_text or texts.get(last_part_id, ""))
                return

    # -- internals ---------------------------------------------------------------

    async def _ensure_session(self, session_id: str) -> PiProcess:
        proc = self._sessions.get(session_id)
        if proc is not None and proc.returncode is None:
            return proc
        # Stale id (app restart or crashed process): re-attach with a
        # fresh pi process. Chat history lives in the desktop store, not
        # in pi, so this only loses pi-side conversational context.
        proc = await self._spawn(title="", workspace_root=self.workspace_root)
        self._sessions[session_id] = proc
        return proc

    async def _spawn(self, title: str, workspace_root: str) -> PiProcess:
        if self._which(self.pi_bin) is None:
            raise HarnessUnavailableError(
                f"pi binary not found on PATH (looked for {self.pi_bin!r})"
            )
        args = [self.pi_bin, "--mode", "rpc"]
        if title:
            args += ["--name", title[:80]]
        try:
            return await self._process_factory(args, workspace_root)
        except OSError as e:
            raise HarnessUnavailableError(f"failed to spawn pi: {e}") from e

    async def _command(
        self, proc: PiProcess, command: dict[str, Any]
    ) -> dict[str, Any]:
        """Send one command and read lines until its response arrives."""
        command_id = command.setdefault("id", uuid.uuid4().hex)
        await _send(proc, command)
        deadline = asyncio.get_running_loop().time() + _COMMAND_TIMEOUT
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise HarnessError(f"pi did not answer {command['type']} in time")
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), remaining)
            except asyncio.TimeoutError:
                raise HarnessError(f"pi did not answer {command['type']} in time")
            if not line:
                raise HarnessError("pi process exited before responding")
            event = _parse_line(line)
            if (
                isinstance(event, dict)
                and event.get("type") == "response"
                and event.get("id") == command_id
            ):
                if event.get("success") is False:
                    raise HarnessError(str(event.get("error") or "pi command failed"))
                return event


async def _send(proc: PiProcess, command: dict[str, Any]) -> None:
    proc.stdin.write((json.dumps(command) + "\n").encode("utf-8"))
    await proc.stdin.drain()


async def _terminate(proc: PiProcess) -> None:
    if proc.returncode is not None:
        return
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        pass


def _parse_line(line: bytes) -> dict[str, Any] | None:
    # Strict JSONL: split on LF only, tolerate a trailing CR.
    raw = line.rstrip(b"\r\n")
    if not raw:
        return None
    try:
        event = json.loads(raw)
    except ValueError:
        return None
    return event if isinstance(event, dict) else None


def _tool_title(args: dict[str, Any] | None) -> str:
    if not args:
        return ""
    title = str(args.get("filePath") or args.get("path") or args.get("command") or "")
    return title[:200]


def _content_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    chunks = [
        str(block.get("text") or "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "\n".join(chunk for chunk in chunks if chunk)


def _last_assistant_text(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        text = _content_text(content)
        if text:
            return text
    return ""
