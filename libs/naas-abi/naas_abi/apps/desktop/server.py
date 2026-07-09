"""FastAPI backend for ABI Desktop.

Local-only HTTP API consumed by the bundled web UI:

- ``/api/chats``        chat CRUD + SSE streaming through the harness port
- ``/api/files``        workspace file explorer (scoped to workspace root)
- ``/api/models``       models exposed by the selected harness
- ``/api/sparql``       embedded Oxigraph SPARQL endpoint
- ``/api/settings``     app settings (workspace root, harness, model)
- ``/api/terminal/ws``  PTY-backed shell over WebSocket
- ``/``                 static frontend from ``web/``
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import signal
import struct
import subprocess
import termios
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .desktop_config import (
    APP_NAME,
    DATA_DIR,
    DB_PATH,
    GRAPH_DIR,
    build_shell_env_source,
    ensure_dirs,
    ensure_workspace,
    workspace_env_report,
)
from .doctor import OpencodeProbe, run_doctor
from .graph import DesktopGraph
from .harness import HarnessPort, HarnessUnavailableError, create_harness
from .harness.adapters.opencode import OpencodeHarnessAdapter
from .integrations import create_integrations_router
from .opencode_client import OpencodeClient, OpencodeUnavailableError
from .store import DesktopStore


def _web_dir() -> Path:
    # Works from source and from a PyInstaller bundle, as long as the
    # spec ships the assets next to this module (see abi-desktop.spec).
    return Path(__file__).parent / "web"


class SettingsUpdate(BaseModel):
    workspace_root: str | None = None
    harness: str | None = None
    opencode_bin: str | None = None
    pi_bin: str | None = None
    default_model: str | None = None
    chat_agent: str | None = None
    code_agent: str | None = None
    doctor_dismissed: str | None = None


class ChatCreate(BaseModel):
    title: str = "New chat"
    section: str = "chat"
    model: str | None = None


class ChatUpdate(BaseModel):
    title: str | None = None
    model: str | None = None


class MessageSend(BaseModel):
    text: str
    model: str | None = None


class FileWrite(BaseModel):
    path: str
    content: str = ""


class FileMkdir(BaseModel):
    path: str


class FileRename(BaseModel):
    path: str
    new_path: str


class SparqlQuery(BaseModel):
    query: str


def _opencode_probe(harness: HarnessPort) -> OpencodeProbe:
    """Sync reachability probe for the doctor (opencode harness only)."""
    if isinstance(harness, OpencodeHarnessAdapter):
        return harness.client

    class _Unreachable:
        def is_running(self) -> bool:
            return False

    return _Unreachable()


def create_app(
    store: DesktopStore | None = None,
    graph: DesktopGraph | None = None,
    harness: HarnessPort | None = None,
    opencode: OpencodeClient | None = None,
) -> FastAPI:
    """Build the FastAPI app.

    ``store``, ``graph`` and ``harness`` are injectable for tests; when
    omitted the app self-provisions under the default data dir
    (``~/.abi-desktop``), preserving production behavior. ``opencode`` is
    a legacy test seam that wraps an injected client in
    :class:`OpencodeHarnessAdapter`.
    """
    if store is None or graph is None:
        ensure_dirs()

    app = FastAPI(title=APP_NAME)
    store = store if store is not None else DesktopStore(DB_PATH)
    graph = graph if graph is not None else DesktopGraph(GRAPH_DIR)
    settings = store.get_settings()
    if harness is None:
        if opencode is not None:
            harness = OpencodeHarnessAdapter(
                workspace_root=settings["workspace_root"],
                client=opencode,
            )
        else:
            harness = create_harness(settings)
    # One in-flight generation per chat, so we can abort cleanly.
    active_sessions: dict[str, str] = {}

    app.state.store = store
    app.state.graph = graph
    app.state.harness = harness

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await harness.stop()
        store.close()

    # -- health / settings ---------------------------------------------------

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        settings = store.get_settings()
        running = await harness.health()
        opencode_url: str | None = None
        if running and isinstance(harness, OpencodeHarnessAdapter):
            try:
                opencode_url = harness.client.base_url
            except AttributeError:
                opencode_url = None
        return {
            "app": APP_NAME,
            "data_dir": str(DATA_DIR),
            "workspace_root": settings.get("workspace_root", ""),
            "harness": settings.get("harness") or "opencode",
            "opencode_running": running,
            "opencode_url": opencode_url,
            "graph": graph.stats(),
        }

    @app.get("/api/doctor")
    async def doctor() -> dict[str, Any]:
        settings = store.get_settings()
        return await run_doctor(
            settings=settings,
            opencode=_opencode_probe(harness),
            data_dir=DATA_DIR,
            db_path=DB_PATH,
            graph_dir=GRAPH_DIR,
        )

    @app.get("/api/settings")
    def get_settings() -> dict[str, str]:
        return store.get_settings()

    @app.get("/api/workspace/env")
    def workspace_env(
        workspace_root: str | None = Query(default=None),
    ) -> dict[str, Any]:
        settings = store.get_settings()
        root = workspace_root or settings.get("workspace_root") or ""
        return workspace_env_report(root)

    @app.put("/api/settings")
    async def put_settings(update: SettingsUpdate) -> dict[str, str]:
        nonlocal harness
        values = {k: v for k, v in update.model_dump().items() if v is not None}
        prior = store.get_settings()
        updated = store.update_settings(values)
        harness_keys = ("workspace_root", "harness", "opencode_bin", "pi_bin")
        if any(key in values for key in harness_keys):
            ensure_workspace(Path(updated["workspace_root"]))
            if "harness" in values and values["harness"] != prior.get("harness"):
                await harness.stop()
                harness = create_harness(updated)
                app.state.harness = harness
            else:
                binary = (
                    updated.get("opencode_bin")
                    if (updated.get("harness") or "opencode") == "opencode"
                    else updated.get("pi_bin")
                )
                try:
                    await harness.restart(
                        workspace_root=updated.get("workspace_root"),
                        binary=binary,
                    )
                except HarnessUnavailableError:
                    pass
        return updated

    # -- models ---------------------------------------------------------------

    @app.get("/api/models")
    async def models() -> dict[str, Any]:
        try:
            await harness.start()
            providers = await harness.list_models()
        except HarnessUnavailableError as e:
            return {"providers": [], "error": str(e)}
        return {"providers": [provider.to_dict() for provider in providers]}

    # -- integrations -----------------------------------------------------------

    def _on_integration_config_change() -> None:
        # Ollama models enter /api/models only after opencode reloads the
        # workspace opencode.json; bounce it if it's already up.
        if isinstance(harness, OpencodeHarnessAdapter) and harness.client.is_running():
            try:
                harness.client.restart()
            except OpencodeUnavailableError:
                pass

    app.include_router(
        create_integrations_router(
            store, on_config_change=_on_integration_config_change
        )
    )

    # -- chats ----------------------------------------------------------------

    @app.get("/api/chats")
    def list_chats(section: str | None = None) -> list[dict[str, Any]]:
        return store.list_chats(section)

    @app.post("/api/chats")
    def create_chat(body: ChatCreate) -> dict[str, Any]:
        chat = store.create_chat(
            title=body.title, section=body.section, model=body.model
        )
        graph.record_chat(chat)
        return chat

    @app.get("/api/chats/{chat_id}")
    def get_chat(chat_id: str) -> dict[str, Any]:
        chat = store.get_chat(chat_id)
        if chat is None:
            raise HTTPException(404, "chat not found")
        return chat

    @app.patch("/api/chats/{chat_id}")
    def patch_chat(chat_id: str, body: ChatUpdate) -> dict[str, Any]:
        chat = store.get_chat(chat_id)
        if chat is None:
            raise HTTPException(404, "chat not found")
        updates = body.model_dump(exclude_unset=True)
        if not updates:
            return chat
        fields: dict[str, Any] = {}
        if "title" in updates:
            fields["title"] = updates["title"]
        if "model" in updates:
            fields["model"] = updates["model"] or None
        updated = store.update_chat(chat_id, **fields)
        assert updated is not None
        return updated

    @app.delete("/api/chats/{chat_id}")
    def delete_chat(chat_id: str) -> dict[str, str]:
        store.delete_chat(chat_id)
        graph.delete_chat(chat_id)
        return {"status": "deleted"}

    @app.get("/api/chats/{chat_id}/messages")
    def list_messages(chat_id: str) -> list[dict[str, Any]]:
        return store.list_messages(chat_id)

    @app.post("/api/chats/{chat_id}/abort")
    async def abort_chat(chat_id: str) -> dict[str, str]:
        session_id = active_sessions.get(chat_id)
        if session_id:
            try:
                await harness.abort(session_id)
            except Exception:
                pass
        return {"status": "aborted"}

    @app.post("/api/chats/{chat_id}/messages")
    async def send_message(chat_id: str, body: MessageSend) -> StreamingResponse:
        chat = store.get_chat(chat_id)
        if chat is None:
            raise HTTPException(404, "chat not found")

        settings = store.get_settings()
        model = body.model or chat.get("model") or settings.get("default_model") or None
        agent = (
            settings.get("code_agent")
            if chat["section"] == "code"
            else settings.get("chat_agent")
        ) or None

        try:
            await harness.start()
        except HarnessUnavailableError as e:
            raise HTTPException(503, f"opencode unavailable: {e}")

        session_id = chat.get("opencode_session_id")
        if not session_id:
            session_id = await harness.create_session(title=chat["title"])
            store.update_chat(chat_id, opencode_session_id=session_id)

        user_message = store.add_message(chat_id, "user", body.text)
        graph.record_message(user_message)

        if chat["title"] == "New chat":
            store.update_chat(chat_id, title=body.text[:60])

        active_sessions[chat_id] = session_id

        async def event_stream() -> AsyncIterator[str]:
            final_text = ""
            # Latest state per tool call, keyed by call id (a call streams
            # pending -> running -> completed snapshots).
            tool_parts: dict[str, dict[str, Any]] = {}
            try:
                async for event in harness.stream_prompt(
                    session_id, body.text, model=model, agent=agent
                ):
                    wire = event.to_dict()
                    if wire["type"] == "complete":
                        final_text = wire.get("text") or final_text
                    elif wire["type"] == "text":
                        final_text = wire.get("text") or final_text
                    elif wire["type"] == "tool":
                        key = wire.get("call_id") or f"{wire['tool']}:{len(tool_parts)}"
                        merged = {**tool_parts.get(key, {}), **wire}
                        if not merged.get("title"):
                            merged["title"] = tool_parts.get(key, {}).get("title", "")
                        tool_parts[key] = merged
                    yield f"data: {json.dumps(wire)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            finally:
                active_sessions.pop(chat_id, None)
                parts = list(tool_parts.values())
                if final_text or parts:
                    assistant_message = store.add_message(
                        chat_id, "assistant", final_text, parts=parts
                    )
                    graph.record_message(assistant_message)
                yield f"data: {json.dumps({'type': 'end'})}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # -- files (workspace explorer) --------------------------------------------

    def _workspace_root() -> Path:
        return Path(store.get_settings()["workspace_root"]).resolve()

    def _safe_path(relative: str) -> Path:
        root = _workspace_root()
        target = (root / relative.lstrip("/")).resolve()
        if not str(target).startswith(str(root)):
            raise HTTPException(400, "path escapes workspace")
        return target

    @app.get("/api/files")
    def list_files(path: str = Query(default="")) -> dict[str, Any]:
        target = _safe_path(path)
        if not target.exists():
            return {"path": path, "entries": []}
        if not target.is_dir():
            raise HTTPException(400, "not a directory")
        entries = []
        for child in sorted(
            target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
        ):
            if child.name.startswith(".git"):
                continue
            entries.append(
                {
                    "name": child.name,
                    "path": str(child.relative_to(_workspace_root())),
                    "is_dir": child.is_dir(),
                    "size": child.stat().st_size if child.is_file() else None,
                }
            )
        return {"path": path, "entries": entries}

    @app.get("/api/files/index")
    def index_files(limit: int = Query(default=5000, ge=1, le=20000)) -> dict[str, Any]:
        """Flat recursive list of workspace-relative file paths for @-mentions."""
        skip_dirs = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            ".mypy_cache",
            ".ruff_cache",
            ".pytest_cache",
            "dist",
            "build",
            ".next",
            ".cache",
        }
        skip_files = {".DS_Store"}
        root = _workspace_root()
        files: list[str] = []
        truncated = False

        def walk(directory: Path) -> None:
            nonlocal truncated
            if truncated:
                return
            try:
                children = sorted(
                    directory.iterdir(), key=lambda p: (not p.is_file(), p.name.lower())
                )
            except OSError:
                return
            for child in children:
                if truncated:
                    return
                if child.is_file():
                    if child.name in skip_files:
                        continue
                    if len(files) >= limit:
                        truncated = True
                        return
                    files.append(str(child.relative_to(root)))
                elif child.is_dir():
                    if child.name in skip_dirs or child.name.startswith(".git"):
                        continue
                    walk(child)

        if root.is_dir():
            walk(root)
        return {"files": files, "truncated": truncated}

    @app.get("/api/files/content")
    def read_file(path: str) -> dict[str, Any]:
        target = _safe_path(path)
        if not target.is_file():
            raise HTTPException(404, "file not found")
        if target.stat().st_size > 2_000_000:
            raise HTTPException(413, "file too large to open")
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(415, "binary file")
        return {"path": path, "content": content}

    @app.put("/api/files/content")
    def write_file(body: FileWrite) -> dict[str, str]:
        target = _safe_path(body.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body.content, encoding="utf-8")
        return {"status": "saved", "path": body.path}

    @app.delete("/api/files")
    def delete_file(path: str) -> dict[str, str]:
        target = _safe_path(path)
        if target.is_dir():
            import shutil

            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        return {"status": "deleted", "path": path}

    @app.post("/api/files/mkdir")
    def make_dir(body: FileMkdir) -> dict[str, str]:
        target = _safe_path(body.path)
        target.mkdir(parents=True, exist_ok=True)
        return {"status": "created", "path": body.path}

    @app.post("/api/files/rename")
    def rename_file(body: FileRename) -> dict[str, str]:
        source = _safe_path(body.path)
        dest = _safe_path(body.new_path)
        if not source.exists():
            raise HTTPException(404, "source not found")
        if dest.exists():
            raise HTTPException(409, "destination already exists")
        dest.parent.mkdir(parents=True, exist_ok=True)
        source.rename(dest)
        return {"status": "renamed", "path": body.path, "new_path": body.new_path}

    # -- terminal (PTY over WebSocket) -----------------------------------------

    @app.websocket("/api/terminal/ws")
    async def terminal_ws(ws: WebSocket) -> None:
        await ws.accept()
        loop = asyncio.get_running_loop()
        master_fd, slave_fd = pty.openpty()

        def _preexec() -> None:
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        env = {**os.environ, "TERM": "xterm-256color"}
        workspace = str(_workspace_root())
        shell_cmd = f"{build_shell_env_source(workspace)} exec bash -l"
        proc = subprocess.Popen(
            ["bash", "-lc", shell_cmd],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=workspace,
            env=env,
            preexec_fn=_preexec,
            close_fds=True,
        )
        os.close(slave_fd)

        pty_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        def _on_pty_readable() -> None:
            try:
                data = os.read(master_fd, 65536)
            except OSError:
                data = b""
            if data:
                pty_queue.put_nowait(data)
            else:
                loop.remove_reader(master_fd)
                pty_queue.put_nowait(None)

        loop.add_reader(master_fd, _on_pty_readable)

        async def _pump_pty_to_ws() -> None:
            while True:
                data = await pty_queue.get()
                if data is None:
                    break
                await ws.send_text(data.decode("utf-8", errors="replace"))

        pump = asyncio.create_task(_pump_pty_to_ws())
        try:
            while True:
                text = await ws.receive_text()
                if text.startswith("{"):
                    try:
                        msg = json.loads(text)
                    except ValueError:
                        msg = None
                    if isinstance(msg, dict) and msg.get("type") == "resize":
                        size = struct.pack(
                            "HHHH", int(msg["rows"]), int(msg["cols"]), 0, 0
                        )
                        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, size)
                        continue
                os.write(master_fd, text.encode())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            pump.cancel()
            try:
                loop.remove_reader(master_fd)
            except (ValueError, OSError):
                pass
            try:
                os.close(master_fd)
            except OSError:
                pass
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGHUP)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    # -- sparql -----------------------------------------------------------------

    @app.post("/api/sparql")
    def sparql(body: SparqlQuery) -> dict[str, Any]:
        try:
            return graph.query(body.query)
        except Exception as e:
            raise HTTPException(400, f"SPARQL error: {e}")

    # -- static frontend ----------------------------------------------------------

    web_dir = _web_dir()

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

    return app
