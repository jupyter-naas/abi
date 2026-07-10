"""FastAPI backend for ABI Desktop.

Local-only HTTP API consumed by the bundled web UI:

- ``/api/chats``        chat CRUD + SSE streaming through the harness port
- ``/api/files``        workspace file explorer (scoped to workspace root)
- ``/api/models``       models exposed by the selected harness
- ``/api/sparql``       embedded Oxigraph SPARQL endpoint
- ``/api/settings``     app settings (workspace root, harness, model)
- ``/api/terminal/ws``  PTY-backed shell over WebSocket
- ``/``                 static frontend from ``gui/web/``
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import shutil
import signal
import struct
import subprocess
import termios
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config.desktop_config import (
    APP_NAME,
    DATA_DIR,
    DB_PATH,
    GRAPH_DIR,
    WORKSPACE_ROOT_VISIBLE,
    add_recent_workspace,
    build_shell_env_source,
    ensure_dirs,
    ensure_workspace,
    maybe_upgrade_workspace_setting,
    parse_recent_workspaces,
    serialize_recent_workspaces,
    validate_workspace_dir,
    workspace_entry,
    workspace_env_report,
)
from ..core.doctor import OpencodeProbe, run_doctor
from ..core.graph import DesktopGraph, tag_intent_from_text
from ..core.integrations import (
    DEFAULT_OLLAMA_BASE_URL,
    OLLAMA_SETTING_KEY,
    create_integrations_router,
    probe_ollama_sync,
)
from ..core.model_capabilities import (
    first_tool_capable_model_ref,
    format_tools_unsupported_error,
    model_supports_tools,
)
from ..core.opencode_client import OpencodeClient, OpencodeUnavailableError
from ..core.store import DesktopStore
from ..core.workspace_layout import (
    DEFAULT_MODEL,
    DEFAULT_ORG,
    build_agent_prompt_prefix,
    list_models,
    list_orgs,
    org_model_path,
    repair_invalid_context_ttl,
    scaffold_org_model,
    sanitize_segment,
    sync_ollama_models_in_instances,
)
from ..harness import HarnessPort, HarnessUnavailableError, create_harness
from ..harness.opencode import OpencodeHarnessAdapter


def _web_dir() -> Path:
    # Works from source and from a PyInstaller bundle, as long as the
    # spec ships the assets next to this module (see abi-desktop.spec).
    return Path(__file__).resolve().parent.parent / "gui" / "web"


def _git_branch(workspace_root: str | Path) -> str | None:
    root = Path(workspace_root).resolve()
    if not (root / ".git").exists():
        return None
    for args in (
        ["git", "branch", "--show-current"],
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    ):
        try:
            result = subprocess.run(
                args,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0:
            continue
        branch = result.stdout.strip()
        if branch and branch != "HEAD":
            return branch
    return None


class OpenWorkspaceRequest(BaseModel):
    path: str


class SettingsUpdate(BaseModel):
    workspace_root: str | None = None
    active_org: str | None = None
    active_model: str | None = None
    harness: str | None = None
    opencode_bin: str | None = None
    pi_bin: str | None = None
    default_model: str | None = None
    chat_agent: str | None = None
    code_agent: str | None = None
    doctor_dismissed: str | None = None
    router_auto_apply: str | None = None


def _truthy_setting(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


class ChatCreate(BaseModel):
    title: str = "New chat"
    section: str = "chat"
    model: str | None = None


class ChatUpdate(BaseModel):
    title: str | None = None
    model: str | None = None


class OpenFileContext(BaseModel):
    path: str
    content: str = ""


class MessageSend(BaseModel):
    text: str
    model: str | None = None
    agent: str | None = None
    open_file: OpenFileContext | None = None


async def _resolve_chat_model(
    harness: HarnessPort,
    *,
    body_model: str | None,
    chat_model: str | None,
    default_model: str | None,
) -> str | None:
    """Pick an explicit model or fall back to the first tool-capable model."""
    for candidate in (body_model, chat_model, default_model):
        if candidate and str(candidate).strip():
            ref = str(candidate).strip()
            if model_supports_tools(ref):
                return ref
    try:
        providers = await harness.list_models()
        return first_tool_capable_model_ref(providers)
    except Exception:
        pass
    return None


class FileWrite(BaseModel):
    path: str
    content: str = ""


class FileMkdir(BaseModel):
    path: str


class FileRename(BaseModel):
    path: str
    new_path: str


class FileImportLocal(BaseModel):
    paths: list[str]
    dir: str = ""


_SKIP_UPLOAD_NAMES = {".DS_Store"}


def _safe_filename(name: str) -> str:
    clean = Path(name).name
    if not clean or clean in {".", ".."}:
        raise HTTPException(400, "invalid filename")
    return clean


def _unique_dest(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    n = 1
    while True:
        candidate = parent / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def _build_open_file_context(section: str, open_file: OpenFileContext | None) -> str:
    """Inject Monaco open-file context for Code section prompts."""
    if section != "code" or open_file is None:
        return ""
    path = (open_file.path or "").strip()
    if not path:
        return ""
    ext = Path(path).suffix.lstrip(".") or "text"
    content = open_file.content or ""
    return (
        "\n\n## Open file in editor\n"
        f"The user is editing `{path}` in Monaco with live HTML preview.\n"
        "Apply changes directly to this file when they ask to modify slides or HTML.\n\n"
        f"```{ext}:{path}\n{content}\n```\n\n"
    )


def _root_entry_sort_key(entry: dict[str, Any]) -> tuple[int, int, str]:
    if entry["name"] == "templates":
        return (0, 0, entry["name"].lower())
    return (1, 0 if entry["is_dir"] else 1, entry["name"].lower())


class SparqlQuery(BaseModel):
    query: str


class RouterSuggestRequest(BaseModel):
    text: str
    prefer_local: bool = True


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
    maybe_upgrade_workspace_setting(store)
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

    def _active_context() -> tuple[str, str]:
        settings = store.get_settings()
        org = settings.get("active_org") or DEFAULT_ORG
        model = settings.get("active_model") or DEFAULT_MODEL
        return org, model

    def _apply_ollama_models_to_context(models: list[dict[str, Any]]) -> None:
        if not models:
            return
        settings = store.get_settings()
        org = settings.get("active_org") or DEFAULT_ORG
        model = settings.get("active_model") or DEFAULT_MODEL
        context_dir = org_model_path(settings["workspace_root"], org, model)
        sync_ollama_models_in_instances(context_dir / "instances.ttl", models)
        graph.load_org_model_context(org, model, context_dir)

    def _sync_ollama_into_active_instances() -> bool:
        settings = store.get_settings()
        base_url = str(
            settings.get(OLLAMA_SETTING_KEY) or DEFAULT_OLLAMA_BASE_URL
        ).rstrip("/")
        probe = probe_ollama_sync(base_url)
        models = probe.get("models") or []
        if not models:
            return False
        org = settings.get("active_org") or DEFAULT_ORG
        model = settings.get("active_model") or DEFAULT_MODEL
        context_dir = org_model_path(settings["workspace_root"], org, model)
        return sync_ollama_models_in_instances(context_dir / "instances.ttl", models)

    def _reload_active_context() -> dict[str, Any]:
        settings = store.get_settings()
        org = settings.get("active_org") or DEFAULT_ORG
        model = settings.get("active_model") or DEFAULT_MODEL
        workspace = Path(settings["workspace_root"]).resolve()
        context_dir = scaffold_org_model(workspace, org, model)
        repair_invalid_context_ttl(workspace, org, model)
        _sync_ollama_into_active_instances()
        return graph.load_org_model_context(org, model, context_dir)

    # Bootstrap default org/model context and graph on startup.
    try:
        _reload_active_context()
    except Exception:
        pass

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
            "active_org": settings.get("active_org") or DEFAULT_ORG,
            "active_model": settings.get("active_model") or DEFAULT_MODEL,
            "harness": settings.get("harness") or "opencode",
            "opencode_running": running,
            "opencode_url": opencode_url,
            "graph": {
                **graph.stats(),
                "routing": graph.active_routing_summary(
                    settings.get("active_org") or DEFAULT_ORG,
                    settings.get("active_model") or DEFAULT_MODEL,
                ),
            },
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

    @app.get("/api/workspace/status")
    async def workspace_status() -> dict[str, Any]:
        settings = store.get_settings()
        workspace_root = settings.get("workspace_root") or ""
        root_path = Path(workspace_root).resolve() if workspace_root else None
        payload: dict[str, Any] = {
            "git_branch": _git_branch(workspace_root) if workspace_root else None,
            "workspace_root": workspace_root,
            "workspace_name": root_path.name if root_path else "",
            "active_org": settings.get("active_org") or DEFAULT_ORG,
            "active_model": settings.get("active_model") or DEFAULT_MODEL,
            "default_model": settings.get("default_model") or "",
            "harness": settings.get("harness") or "opencode",
            "harness_connected": await harness.health(),
            "chat_agent": settings.get("chat_agent") or "plan",
            "code_agent": settings.get("code_agent") or "build",
            "context_tokens": None,
            "cpu_percent": None,
        }
        return payload

    def _workspaces_payload() -> dict[str, Any]:
        settings = store.get_settings()
        active_root = settings.get("workspace_root") or ""
        active = workspace_entry(active_root) if active_root else None
        recent_paths = parse_recent_workspaces(settings.get("recent_workspaces"))
        recent = [workspace_entry(path) for path in recent_paths]
        return {"active": active, "recent": recent}

    async def _restart_harness_for_workspace(
        updated: dict[str, str],
        prior: dict[str, str],
        values: dict[str, str],
    ) -> None:
        nonlocal harness
        harness_keys = ("workspace_root", "harness", "opencode_bin", "pi_bin")
        if not any(key in values for key in harness_keys):
            return
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

    async def _reload_workspace_context(updated: dict[str, str]) -> None:
        workspace = Path(updated["workspace_root"]).resolve()
        org = updated.get("active_org") or DEFAULT_ORG
        model = updated.get("active_model") or DEFAULT_MODEL
        scaffold_org_model(workspace, org, model)
        try:
            _reload_active_context()
        except Exception:
            pass

    @app.get("/api/workspaces")
    def list_workspaces() -> dict[str, Any]:
        return _workspaces_payload()

    @app.post("/api/workspaces/open")
    async def open_workspace(body: OpenWorkspaceRequest) -> dict[str, Any]:
        nonlocal harness
        try:
            resolved = validate_workspace_dir(body.path)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        prior = store.get_settings()
        recent = add_recent_workspace(
            parse_recent_workspaces(prior.get("recent_workspaces")),
            resolved,
        )
        updated = store.update_settings(
            {
                "workspace_root": str(resolved),
                "recent_workspaces": serialize_recent_workspaces(recent),
            }
        )
        await _restart_harness_for_workspace(
            updated, prior, {"workspace_root": str(resolved)}
        )
        await _reload_workspace_context(updated)
        return {
            "settings": updated,
            "workspaces": _workspaces_payload(),
        }

    @app.put("/api/settings")
    async def put_settings(update: SettingsUpdate) -> dict[str, str]:
        nonlocal harness
        values = {k: v for k, v in update.model_dump().items() if v is not None}
        prior = store.get_settings()
        if "active_org" in values:
            values["active_org"] = sanitize_segment(values["active_org"])
        if "active_model" in values:
            values["active_model"] = sanitize_segment(values["active_model"])
        if "workspace_root" in values:
            recent = add_recent_workspace(
                parse_recent_workspaces(prior.get("recent_workspaces")),
                values["workspace_root"],
            )
            values["recent_workspaces"] = serialize_recent_workspaces(recent)
        updated = store.update_settings(values)
        harness_keys = ("workspace_root", "harness", "opencode_bin", "pi_bin")
        if any(key in values for key in harness_keys):
            await _restart_harness_for_workspace(updated, prior, values)
        context_changed = (
            "workspace_root" in values
            or "active_org" in values
            or "active_model" in values
        )
        if context_changed:
            await _reload_workspace_context(updated)
        return updated

    @app.get("/api/workspace/orgs")
    def workspace_orgs() -> dict[str, Any]:
        root = Path(store.get_settings()["workspace_root"]).resolve()
        org, model = _active_context()
        return {
            "orgs": list_orgs(root),
            "active_org": org,
            "active_model": model,
        }

    @app.get("/api/workspace/orgs/{org}/models")
    def workspace_models(org: str) -> dict[str, Any]:
        root = Path(store.get_settings()["workspace_root"]).resolve()
        try:
            safe_org = sanitize_segment(org)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        active_org, active_model = _active_context()
        return {
            "org": safe_org,
            "models": list_models(root, safe_org),
            "active_model": active_model if active_org == safe_org else None,
        }

    @app.post("/api/workspace/orgs/{org}/models/{model}/scaffold")
    def workspace_scaffold(org: str, model: str) -> dict[str, Any]:
        root = Path(store.get_settings()["workspace_root"]).resolve()
        try:
            safe_org = sanitize_segment(org)
            safe_model = sanitize_segment(model)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        path = scaffold_org_model(root, safe_org, safe_model)
        loaded = graph.load_org_model_context(safe_org, safe_model, path)
        return {
            "org": safe_org,
            "model": safe_model,
            "path": str(path.relative_to(root)),
            "files": [
                name
                for name in ("AGENTS.md", "MEMORY.md", "ontology.ttl", "instances.ttl")
                if (path / name).is_file()
            ],
            "graph": loaded,
        }

    # -- models ---------------------------------------------------------------

    @app.get("/api/models")
    async def models() -> dict[str, Any]:
        try:
            await harness.start()
            providers = await harness.list_models()
        except HarnessUnavailableError as e:
            return {"providers": [], "error": str(e)}
        return {"providers": [provider.to_dict() for provider in providers]}

    @app.get("/api/agents")
    def list_agents(section: str = Query(default="chat")) -> dict[str, Any]:
        settings = store.get_settings()
        org, model = _active_context()
        route = graph.resolve_route(org, model, section)
        agents = [
            {
                "id": "plan",
                "name": "Plan",
                "description": "Read-only planning agent",
            },
            {
                "id": "build",
                "name": "Build",
                "description": "Code editing agent",
            },
        ]
        default_agent = "build" if section == "code" else "plan"
        selected = (
            route.get("agent")
            if route and route.get("agent")
            else (
                settings.get("code_agent")
                if section == "code"
                else settings.get("chat_agent")
            )
            or default_agent
        )
        return {"agents": agents, "selected": selected, "section": section}

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
            store,
            on_config_change=_on_integration_config_change,
            on_ollama_models_synced=_apply_ollama_models_to_context,
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
        active_org = settings.get("active_org") or DEFAULT_ORG
        active_model = settings.get("active_model") or DEFAULT_MODEL
        route = graph.resolve_route(active_org, active_model, str(chat["section"]))

        explicit_model = (
            body.model or chat.get("model") or settings.get("default_model")
        )
        has_explicit_model = bool(explicit_model and str(explicit_model).strip())
        router_suggested: str | None = None
        if not has_explicit_model and _truthy_setting(
            settings.get("router_auto_apply")
        ):
            intent_tags = tag_intent_from_text(body.text)
            suggestions = graph.suggest_models(
                intent_tags,
                prefer_local=True,
                org=active_org,
                model=active_model,
            )
            if suggestions:
                ref = suggestions[0].model_ref
                if model_supports_tools(ref):
                    router_suggested = ref

        model = await _resolve_chat_model(
            harness,
            body_model=body.model,
            chat_model=chat.get("model"),
            default_model=settings.get("default_model"),
        )
        if (
            explicit_model
            and str(explicit_model).strip()
            and not model_supports_tools(str(explicit_model).strip())
        ):

            async def unsupported_stream() -> AsyncIterator[str]:
                message = format_tools_unsupported_error(str(explicit_model).strip())
                yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
                yield f"data: {json.dumps({'type': 'end'})}\n\n"

            return StreamingResponse(
                unsupported_stream(), media_type="text/event-stream"
            )

        route_model_hint = route.get("model_hint") if route else None
        if router_suggested and not has_explicit_model:
            model = router_suggested
        elif (
            route_model_hint
            and not has_explicit_model
            and model_supports_tools(route_model_hint)
        ):
            model = route_model_hint

        if model and not chat.get("model") and not body.model:
            store.update_chat(chat_id, model=model)

        workspace = Path(settings["workspace_root"]).resolve()
        route_agent = route.get("agent") if route else None
        agent = (
            body.agent
            or route_agent
            or (
                (
                    settings.get("code_agent")
                    if chat["section"] == "code"
                    else settings.get("chat_agent")
                )
                or None
            )
        )

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

        prompt_prefix = build_agent_prompt_prefix(workspace, active_org, active_model)
        routing_hint = graph.build_routing_prompt_hint(
            active_org, active_model, str(chat["section"])
        )
        if routing_hint:
            prompt_prefix = f"{prompt_prefix}{routing_hint}"
        open_file_ctx = _build_open_file_context(str(chat["section"]), body.open_file)
        prompt_text = f"{prompt_prefix}{open_file_ctx}{body.text}"

        if chat["title"] == "New chat":
            store.update_chat(chat_id, title=body.text[:60])

        active_sessions[chat_id] = session_id

        async def event_stream() -> AsyncIterator[str]:
            final_text = ""
            stream_sources: list[str] = []
            # Latest state per tool call, keyed by call id (a call streams
            # pending -> running -> completed snapshots).
            tool_parts: dict[str, dict[str, Any]] = {}
            try:
                async for event in harness.stream_prompt(
                    session_id, prompt_text, model=model, agent=agent
                ):
                    wire = event.to_dict()
                    if wire["type"] == "complete":
                        final_text = wire.get("text") or final_text
                        raw_sources = wire.get("sources")
                        if isinstance(raw_sources, list):
                            stream_sources = [
                                str(item) for item in raw_sources if str(item).strip()
                            ]
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
                if final_text or parts or stream_sources:
                    assistant_message = store.add_message(
                        chat_id,
                        "assistant",
                        final_text,
                        parts=parts,
                        sources=stream_sources,
                    )
                    graph.record_message(assistant_message)
                if stream_sources:
                    yield f"data: {json.dumps({'type': 'sources', 'sources': stream_sources})}\n\n"
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
    def list_files(
        path: str = Query(default=""),
        show_hidden: bool = Query(default=False),
    ) -> dict[str, Any]:
        target = _safe_path(path)
        if not target.exists():
            return {"path": path, "entries": []}
        if not target.is_dir():
            raise HTTPException(400, "not a directory")
        entries = []
        seen: set[str] = set()
        for child in sorted(
            target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
        ):
            if child.name.startswith(".git"):
                continue
            if child.name.startswith("."):
                at_root = path == "" and child.name in WORKSPACE_ROOT_VISIBLE
                if not show_hidden and not at_root:
                    continue
            rel = str(child.relative_to(_workspace_root()))
            seen.add(rel)
            entries.append(
                {
                    "name": child.name,
                    "path": rel,
                    "is_dir": child.is_dir(),
                    "size": child.stat().st_size if child.is_file() else None,
                }
            )
        if path == "":
            root = _workspace_root()
            for name in WORKSPACE_ROOT_VISIBLE:
                child = root / name
                rel = name
                if rel in seen or child.name.startswith(".git"):
                    continue
                if child.exists():
                    entries.append(
                        {
                            "name": child.name,
                            "path": rel,
                            "is_dir": child.is_dir(),
                            "size": child.stat().st_size if child.is_file() else None,
                        }
                    )
            entries.sort(key=_root_entry_sort_key)
        elif path == "templates":
            entries.sort(key=lambda entry: (not entry["is_dir"], entry["name"].lower()))
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

    @app.post("/api/files/upload")
    async def upload_files(
        dir: str = Form(default=""),
        files: list[UploadFile] = File(...),
    ) -> dict[str, Any]:
        target_dir = _safe_path(dir)
        if target_dir.exists() and not target_dir.is_dir():
            raise HTTPException(400, "not a directory")
        target_dir.mkdir(parents=True, exist_ok=True)
        root = _workspace_root()
        uploaded: list[str] = []
        for upload in files:
            filename = _safe_filename(upload.filename or "")
            if filename in _SKIP_UPLOAD_NAMES:
                continue
            dest = _unique_dest(target_dir / filename)
            dest.write_bytes(await upload.read())
            uploaded.append(str(dest.relative_to(root)))
        return {"status": "uploaded", "uploaded": uploaded}

    @app.post("/api/files/import-local")
    def import_local_files(body: FileImportLocal) -> dict[str, Any]:
        """Copy absolute paths into the workspace (pywebview Finder drop bridge)."""
        target_dir = _safe_path(body.dir)
        if target_dir.exists() and not target_dir.is_dir():
            raise HTTPException(400, "not a directory")
        target_dir.mkdir(parents=True, exist_ok=True)
        root = _workspace_root()
        uploaded: list[str] = []
        skipped: list[str] = []
        for raw in body.paths:
            source = Path(raw).resolve()
            if not source.exists() or not source.is_file():
                skipped.append(raw)
                continue
            if source.name in _SKIP_UPLOAD_NAMES:
                continue
            dest = _unique_dest(target_dir / source.name)
            shutil.copy2(source, dest)
            uploaded.append(str(dest.relative_to(root)))
        return {"status": "imported", "uploaded": uploaded, "skipped": skipped}

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

    # -- model router -----------------------------------------------------------

    @app.post("/api/router/suggest")
    def router_suggest(body: RouterSuggestRequest) -> dict[str, Any]:
        org, model = _active_context()
        intent_tags = tag_intent_from_text(body.text)
        suggestions = graph.suggest_models(
            intent_tags,
            body.prefer_local,
            org=org,
            model=model,
        )
        return {
            "intent_tags": intent_tags,
            "prefer_local": body.prefer_local,
            "suggestions": [item.to_dict() for item in suggestions],
        }

    # -- sparql -----------------------------------------------------------------

    @app.get("/api/graph/overview")
    def graph_overview(view: str = "abox") -> dict[str, Any]:
        settings = store.get_settings()
        org, model = _active_context()
        return graph.build_graph_overview(
            settings=settings,
            chats=store.list_chats(),
            messages=store.list_recent_messages(),
            org=org,
            model=model,
            view=view,
        )

    @app.get("/api/graph/buckets")
    def graph_buckets() -> dict[str, Any]:
        return {"buckets": graph.list_bfo_buckets()}

    @app.get("/api/graph/subclasses")
    def graph_subclasses(iri: str) -> dict[str, Any]:
        org, model = _active_context()
        return {
            "iri": iri,
            "subclasses": graph.query_subclasses(iri, org=org, model=model),
        }

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
