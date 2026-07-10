"""API tests for the ABI Desktop FastAPI backend.

Everything runs against tmp_path-backed store/graph/workspace and a stub
opencode client injected through ``create_app`` — no real opencode binary,
no network, nothing under ``~/.abi-desktop``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient

from desktop.core.graph import ABID, DesktopGraph
from desktop.harness.opencode import OpencodeHarnessAdapter
from desktop.core.opencode_client import OpencodeUnavailableError
from desktop.api.server import create_app
from desktop.core.store import DesktopStore


class StubOpencode:
    """Duck-typed stand-in for OpencodeClient (no process, no HTTP)."""

    def __init__(self) -> None:
        self.script: list[dict[str, Any]] = [{"type": "complete", "text": ""}]
        self.fail_start = False
        self.prompts: list[dict[str, Any]] = []
        self.aborted: list[str] = []
        self.restarts: list[dict[str, Any]] = []
        self._session_counter = 0

    def is_running(self) -> bool:
        return not self.fail_start

    def start(self, startup_timeout: float = 20.0) -> None:
        if self.fail_start:
            raise OpencodeUnavailableError("opencode binary not found")

    def stop(self) -> None:
        pass

    def restart(self, workdir: str | None = None, opencode_bin: str | None = None):
        self.restarts.append({"workdir": workdir, "opencode_bin": opencode_bin})

    async def create_session(self, title: str) -> str:
        self._session_counter += 1
        return f"ses_{self._session_counter}"

    async def providers(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "openai",
                "name": "OpenAI",
                "models": [{"id": "gpt-5", "name": "gpt-5", "supports_tools": True}],
            },
            {
                "id": "ollama",
                "name": "Ollama",
                "models": [
                    {
                        "id": "phi:latest",
                        "name": "phi:latest",
                        "supports_tools": False,
                    },
                    {
                        "id": "qwen2.5-coder:7b",
                        "name": "qwen2.5-coder:7b",
                        "supports_tools": True,
                    },
                ],
            },
        ]

    async def abort(self, session_id: str) -> None:
        self.aborted.append(session_id)

    async def stream_message(
        self,
        session_id: str,
        text: str,
        model: str | None = None,
        agent: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        self.prompts.append(
            {"session_id": session_id, "text": text, "model": model, "agent": agent}
        )
        for event in self.script:
            yield event


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture()
def store(tmp_path: Path, workspace: Path) -> Iterator[DesktopStore]:
    s = DesktopStore(tmp_path / "desktop.db")
    s.update_settings({"workspace_root": str(workspace)})
    yield s


@pytest.fixture()
def graph(tmp_path: Path) -> Iterator[DesktopGraph]:
    g = DesktopGraph(tmp_path / "graph")
    yield g
    g.close()


@pytest.fixture()
def opencode() -> StubOpencode:
    return StubOpencode()


@pytest.fixture()
def client(
    store: DesktopStore, graph: DesktopGraph, opencode: StubOpencode
) -> Iterator[TestClient]:
    harness = OpencodeHarnessAdapter(
        workspace_root=store.get_settings()["workspace_root"],
        client=opencode,  # type: ignore[arg-type]
    )
    app = create_app(store=store, graph=graph, harness=harness)
    with TestClient(app) as test_client:
        yield test_client


def _sse_frames(body: str) -> list[dict[str, Any]]:
    return [
        json.loads(line.removeprefix("data:").strip())
        for line in body.splitlines()
        if line.startswith("data:")
    ]


# -- health / settings --------------------------------------------------------


def test_health(client: TestClient, workspace: Path) -> None:
    payload = client.get("/api/health").json()
    assert payload["opencode_running"] is True
    assert payload["graph"]["triples"] >= 0
    assert payload["graph"]["active_context"] == {"org": "default", "model": "default"}
    assert payload["workspace_root"] == str(workspace)
    assert payload["active_org"] == "default"
    assert payload["active_model"] == "default"
    assert "data_dir" in payload
    assert payload["harness"] == "opencode"


def test_settings_get_and_put(client: TestClient, workspace: Path) -> None:
    settings = client.get("/api/settings").json()
    assert settings["workspace_root"] == str(workspace)

    updated = client.put("/api/settings", json={"default_model": "openai/gpt-5"})
    assert updated.status_code == 200
    assert updated.json()["default_model"] == "openai/gpt-5"
    assert client.get("/api/settings").json()["default_model"] == "openai/gpt-5"


def test_settings_workspace_change_restarts_opencode(
    client: TestClient, tmp_path: Path, opencode: StubOpencode
) -> None:
    new_ws = tmp_path / "other-workspace"
    response = client.put("/api/settings", json={"workspace_root": str(new_ws)})
    assert response.status_code == 200
    assert new_ws.is_dir()
    assert opencode.restarts == [{"workdir": str(new_ws), "opencode_bin": "opencode"}]


def test_workspace_env_endpoint_reports_files(
    client: TestClient, workspace: Path
) -> None:
    (workspace / ".env").write_text("OPENAI_API_KEY=sk-test\n")
    payload = client.get("/api/workspace/env").json()
    assert payload["workspace_root"] == str(workspace.resolve())
    assert payload["has_provider_keys"] is True
    assert "OPENAI_API_KEY" in payload["provider_keys"]
    env_entry = next(item for item in payload["files"] if item["name"] == ".env")
    assert env_entry["exists"] is True
    assert "OPENAI_API_KEY" in env_entry["keys"]
    assert "sk-test" not in str(payload)


def test_workspace_env_preview_uses_query_param(
    client: TestClient, tmp_path: Path
) -> None:
    preview = tmp_path / "preview"
    preview.mkdir()
    (preview / ".env.remote").write_text("ANTHROPIC_API_KEY=secret\n")
    payload = client.get(
        "/api/workspace/env", params={"workspace_root": str(preview)}
    ).json()
    assert payload["workspace_root"] == str(preview.resolve())
    assert "ANTHROPIC_API_KEY" in payload["provider_keys"]


def test_workspaces_list_returns_active_and_recent(
    client: TestClient, workspace: Path, tmp_path: Path
) -> None:
    other = tmp_path / "other-project"
    other.mkdir()
    client.put("/api/settings", json={"workspace_root": str(workspace)})
    client.post("/api/workspaces/open", json={"path": str(other)})

    payload = client.get("/api/workspaces").json()
    assert payload["active"]["path"] == str(other.resolve())
    assert payload["active"]["name"] == "other-project"
    assert payload["active"]["exists"] is True
    recent_paths = [item["path"] for item in payload["recent"]]
    assert str(other.resolve()) in recent_paths
    assert str(workspace.resolve()) in recent_paths


def test_workspaces_open_sets_active_and_adds_recent(
    client: TestClient, workspace: Path, tmp_path: Path, opencode: StubOpencode
) -> None:
    target = tmp_path / "opened"
    target.mkdir()
    (target / "marker.txt").write_text("ok")

    response = client.post("/api/workspaces/open", json={"path": str(target)})
    assert response.status_code == 200
    body = response.json()
    assert body["settings"]["workspace_root"] == str(target.resolve())
    assert body["workspaces"]["active"]["name"] == "opened"
    assert opencode.restarts[-1]["workdir"] == str(target.resolve())


def test_workspaces_open_invalid_path_400(client: TestClient) -> None:
    response = client.post(
        "/api/workspaces/open", json={"path": "/no/such/workspace/folder"}
    )
    assert response.status_code == 400


def test_workspaces_switch_updates_file_listing_root(
    client: TestClient, workspace: Path, tmp_path: Path
) -> None:
    other = tmp_path / "listing-root"
    other.mkdir()
    (other / "only-here.txt").write_text("x")
    (workspace / "only-here.txt").write_text("y")

    client.post("/api/workspaces/open", json={"path": str(other)})
    listing = client.get("/api/files").json()
    names = [entry["name"] for entry in listing["entries"]]
    assert "only-here.txt" in names
    assert client.get("/api/files/content", params={"path": "only-here.txt"}).json()[
        "content"
    ] == "x"


def test_workspace_status_reports_git_and_harness(
    client: TestClient, workspace: Path, opencode: StubOpencode
) -> None:
    subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(
        ["git", "checkout", "-b", "feature/status"],
        cwd=workspace,
        check=True,
        capture_output=True,
    )

    client.put(
        "/api/settings",
        json={
            "default_model": "openai/gpt-5",
            "chat_agent": "plan",
            "code_agent": "build",
        },
    )

    payload = client.get("/api/workspace/status").json()
    assert payload["git_branch"] == "feature/status"
    assert payload["workspace_root"] == str(workspace.resolve())
    assert payload["workspace_name"] == workspace.name
    assert payload["active_org"] == "default"
    assert payload["active_model"] == "default"
    assert payload["default_model"] == "openai/gpt-5"
    assert payload["harness"] == "opencode"
    assert payload["harness_connected"] is True
    assert payload["chat_agent"] == "plan"
    assert payload["code_agent"] == "build"
    assert payload["context_tokens"] is None
    assert payload["cpu_percent"] is None

    opencode.fail_start = True
    payload = client.get("/api/workspace/status").json()
    assert payload["harness_connected"] is False


def test_settings_active_org_model(client: TestClient, workspace: Path) -> None:
    updated = client.put(
        "/api/settings", json={"active_org": "acme", "active_model": "coder"}
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["active_org"] == "acme"
    assert body["active_model"] == "coder"
    assert (workspace / "acme" / "coder" / "AGENTS.md").is_file()


def test_workspace_orgs_and_models(client: TestClient, workspace: Path) -> None:
    client.put("/api/settings", json={"active_org": "alpha", "active_model": "fast"})
    client.post("/api/workspace/orgs/alpha/models/slow/scaffold")
    client.post("/api/workspace/orgs/beta/models/main/scaffold")

    orgs = client.get("/api/workspace/orgs").json()
    assert orgs["active_org"] == "alpha"
    assert orgs["active_model"] == "fast"
    assert set(orgs["orgs"]) == {"alpha", "beta", "default"}

    models = client.get("/api/workspace/orgs/alpha/models").json()
    assert models["models"] == ["fast", "slow"]
    assert models["active_model"] == "fast"


def test_workspace_scaffold_endpoint(client: TestClient, workspace: Path) -> None:
    payload = client.post("/api/workspace/orgs/demo/models/test/scaffold").json()
    assert payload["org"] == "demo"
    assert payload["model"] == "test"
    assert payload["path"] == "demo/test"
    assert "AGENTS.md" in payload["files"]
    assert (workspace / "demo" / "test" / "ontology.ttl").is_file()


def test_health_includes_active_context(client: TestClient) -> None:
    client.put("/api/settings", json={"active_org": "acme", "active_model": "coder"})
    payload = client.get("/api/health").json()
    assert payload["active_org"] == "acme"
    assert payload["active_model"] == "coder"


# -- models --------------------------------------------------------------------


def test_models(client: TestClient) -> None:
    payload = client.get("/api/models").json()
    assert payload["providers"][0]["id"] == "openai"


def test_models_degrades_when_opencode_unavailable(
    client: TestClient, opencode: StubOpencode
) -> None:
    opencode.fail_start = True
    payload = client.get("/api/models").json()
    assert payload["providers"] == []
    assert "not found" in payload["error"]


# -- chats CRUD ------------------------------------------------------------------


def test_chat_crud_roundtrip(client: TestClient) -> None:
    created = client.post(
        "/api/chats", json={"title": "T", "section": "code", "model": "m"}
    ).json()
    assert created["title"] == "T"

    assert client.get(f"/api/chats/{created['id']}").json() == created
    assert [c["id"] for c in client.get("/api/chats").json()] == [created["id"]]
    assert client.get("/api/chats", params={"section": "chat"}).json() == []

    assert client.delete(f"/api/chats/{created['id']}").json() == {"status": "deleted"}
    assert client.get(f"/api/chats/{created['id']}").status_code == 404


def test_chat_create_records_graph_triples(client: TestClient) -> None:
    chat = client.post("/api/chats", json={"title": "Graphed"}).json()
    result = client.post(
        "/api/sparql",
        json={
            "query": f"SELECT ?t WHERE {{ <{ABID}chat/{chat['id']}> <{ABID}title> ?t }}"
        },
    ).json()
    assert result["rows"] == [{"t": "Graphed"}]


def test_chat_delete_removes_graph_triples(client: TestClient) -> None:
    chat = client.post("/api/chats", json={"title": "Gone"}).json()
    client.delete(f"/api/chats/{chat['id']}")
    result = client.post(
        "/api/sparql",
        json={"query": f"ASK {{ <{ABID}chat/{chat['id']}> ?p ?o }}"},
    ).json()
    assert result == {"type": "boolean", "value": False}


def test_get_missing_chat_404(client: TestClient) -> None:
    assert client.get("/api/chats/nope").status_code == 404


def test_patch_chat_model(client: TestClient) -> None:
    chat = client.post("/api/chats", json={"title": "M"}).json()
    assert chat["model"] is None

    updated = client.patch(
        f"/api/chats/{chat['id']}", json={"model": "ollama/gemma4:latest"}
    )
    assert updated.status_code == 200
    assert updated.json()["model"] == "ollama/gemma4:latest"
    assert (
        client.get(f"/api/chats/{chat['id']}").json()["model"] == "ollama/gemma4:latest"
    )

    cleared = client.patch(f"/api/chats/{chat['id']}", json={"model": ""})
    assert cleared.status_code == 200
    assert cleared.json()["model"] is None


def test_patch_missing_chat_404(client: TestClient) -> None:
    assert client.patch("/api/chats/nope", json={"model": "x"}).status_code == 404


# -- messages / SSE streaming ------------------------------------------------------


def test_send_message_streams_and_persists(
    client: TestClient, store: DesktopStore, opencode: StubOpencode
) -> None:
    opencode.script = [
        {"type": "text", "text": "Hi", "part_id": "prt_1"},
        {"type": "text", "text": "Hi there", "part_id": "prt_1"},
        {
            "type": "tool",
            "tool": "read",
            "status": "completed",
            "title": "a.py",
            "call_id": "call_1",
        },
        {"type": "complete", "text": "Hi there"},
    ]
    chat = client.post("/api/chats", json={}).json()

    response = client.post(f"/api/chats/{chat['id']}/messages", json={"text": "hello"})
    assert response.status_code == 200
    frames = _sse_frames(response.text)
    assert [f["type"] for f in frames] == ["text", "text", "tool", "complete", "end"]

    messages = client.get(f"/api/chats/{chat['id']}/messages").json()
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "hello"),
        ("assistant", "Hi there"),
    ]
    assert messages[1]["parts"][0]["tool"] == "read"

    # Session is created once and stored; title adopts the first prompt.
    refreshed = client.get(f"/api/chats/{chat['id']}").json()
    assert refreshed["opencode_session_id"] == "ses_1"
    assert refreshed["title"] == "hello"
    assert opencode.prompts[0]["agent"] == "plan"


def test_list_agents_for_section(client: TestClient) -> None:
    chat_agents = client.get("/api/agents?section=chat").json()
    code_agents = client.get("/api/agents?section=code").json()
    assert chat_agents["selected"] == "plan"
    assert code_agents["selected"] == "build"
    assert {agent["id"] for agent in chat_agents["agents"]} == {"plan", "build"}


def test_send_message_agent_override(
    client: TestClient, opencode: StubOpencode
) -> None:
    opencode.script = [{"type": "complete", "text": "ok"}]
    chat = client.post("/api/chats", json={}).json()
    client.post(
        f"/api/chats/{chat['id']}/messages",
        json={"text": "hello", "agent": "build"},
    )
    assert opencode.prompts[0]["agent"] == "build"


def test_send_message_persists_sources_from_complete(
    client: TestClient, opencode: StubOpencode
) -> None:
    opencode.script = [
        {"type": "complete", "text": "Done", "sources": ["policy.pdf"]},
    ]
    chat = client.post("/api/chats", json={}).json()
    response = client.post(f"/api/chats/{chat['id']}/messages", json={"text": "hello"})
    frames = _sse_frames(response.text)
    assert any(f.get("type") == "sources" for f in frames)
    messages = client.get(f"/api/chats/{chat['id']}/messages").json()
    assert messages[1]["sources"] == ["policy.pdf"]


def test_send_message_reuses_session_and_code_agent(
    client: TestClient, opencode: StubOpencode
) -> None:
    chat = client.post("/api/chats", json={"section": "code"}).json()
    client.post(f"/api/chats/{chat['id']}/messages", json={"text": "one"})
    client.post(f"/api/chats/{chat['id']}/messages", json={"text": "two"})

    assert [p["session_id"] for p in opencode.prompts] == ["ses_1", "ses_1"]
    assert all(p["agent"] == "build" for p in opencode.prompts)


def test_send_message_injects_agent_context(
    client: TestClient, workspace: Path, opencode: StubOpencode, store: DesktopStore
) -> None:
    store.update_settings({"active_org": "acme", "active_model": "coder"})
    context = workspace / "acme" / "coder"
    context.mkdir(parents=True)
    (context / "AGENTS.md").write_text("# Rules\nAlways test.\n", encoding="utf-8")
    (context / "MEMORY.md").write_text(
        "# Memory\nProject uses pytest.\n", encoding="utf-8"
    )

    chat = client.post("/api/chats", json={}).json()
    client.post(f"/api/chats/{chat['id']}/messages", json={"text": "hello"})

    prompt = opencode.prompts[-1]["text"]
    assert "Always test." in prompt
    assert "Project uses pytest." in prompt
    assert prompt.endswith("hello")
    messages = client.get(f"/api/chats/{chat['id']}/messages").json()
    assert messages[0]["content"] == "hello"


def test_send_message_uses_graph_route_agent_and_hint(
    client: TestClient, workspace: Path, opencode: StubOpencode, store: DesktopStore
) -> None:
    from desktop.core.workspace_layout import scaffold_org_model

    store.update_settings({"active_org": "route", "active_model": "test"})
    context = scaffold_org_model(workspace, "route", "test")
    instances = (context / "instances.ttl").read_text(encoding="utf-8")
    (context / "instances.ttl").write_text(
        instances.replace(
            'abid:harnessAgent "plan"', 'abid:harnessAgent "custom-chat"'
        ),
        encoding="utf-8",
    )
    client.put("/api/settings", json={"active_org": "route", "active_model": "test"})

    chat = client.post("/api/chats", json={}).json()
    client.post(f"/api/chats/{chat['id']}/messages", json={"text": "route me"})

    assert opencode.prompts[-1]["agent"] == "custom-chat"
    prompt = opencode.prompts[-1]["text"]
    assert "Routing (knowledge graph)" in prompt
    assert "Harness agent: `custom-chat`" in prompt


def test_send_message_uses_graph_route_model_hint(
    client: TestClient, workspace: Path, opencode: StubOpencode, store: DesktopStore
) -> None:
    from desktop.core.workspace_layout import scaffold_org_model

    store.update_settings({"active_org": "route", "active_model": "model-hint"})
    context = scaffold_org_model(workspace, "route", "model-hint")
    instances = (context / "instances.ttl").read_text(encoding="utf-8")
    (context / "instances.ttl").write_text(
        instances.replace(
            'abid:usesHarness "opencode" ;',
            'abid:usesHarness "opencode" ;\n    abid:harnessModel "ollama/qwen2.5-coder" ;',
            1,
        ),
        encoding="utf-8",
    )
    client.put(
        "/api/settings",
        json={"active_org": "route", "active_model": "model-hint", "default_model": ""},
    )

    chat = client.post("/api/chats", json={}).json()
    client.post(f"/api/chats/{chat['id']}/messages", json={"text": "use graph model"})

    assert opencode.prompts[-1]["model"] == "ollama/qwen2.5-coder"


def test_health_includes_active_routing_summary(
    client: TestClient, workspace: Path, store: DesktopStore
) -> None:
    from desktop.core.workspace_layout import scaffold_org_model

    store.update_settings({"active_org": "health", "active_model": "route"})
    scaffold_org_model(workspace, "health", "route")
    client.put("/api/settings", json={"active_org": "health", "active_model": "route"})

    health = client.get("/api/health").json()
    routing = health["graph"]["routing"]
    assert routing["org"] == "health"
    assert routing["model"] == "route"
    assert routing["chat"]["agent"] == "plan"
    assert routing["code"]["agent"] == "build"


def test_send_message_model_priority(
    client: TestClient, opencode: StubOpencode
) -> None:
    client.put("/api/settings", json={"default_model": "openai/default"})
    chat = client.post("/api/chats", json={"model": "openai/chat-model"}).json()

    client.post(f"/api/chats/{chat['id']}/messages", json={"text": "a"})
    assert opencode.prompts[-1]["model"] == "openai/chat-model"

    client.post(
        f"/api/chats/{chat['id']}/messages",
        json={"text": "b", "model": "openai/override"},
    )
    assert opencode.prompts[-1]["model"] == "openai/override"


def test_send_message_falls_back_to_first_ollama_model(
    client: TestClient, opencode: StubOpencode
) -> None:
    async def ollama_providers() -> list[dict[str, Any]]:
        return [
            {
                "id": "ollama",
                "name": "Ollama",
                "models": [{"id": "gemma4:latest", "name": "gemma4:latest"}],
            }
        ]

    opencode.providers = ollama_providers  # type: ignore[method-assign]
    chat = client.post("/api/chats", json={}).json()

    client.post(f"/api/chats/{chat['id']}/messages", json={"text": "hello"})

    assert opencode.prompts[-1]["model"] == "ollama/gemma4:latest"
    assert (
        client.get(f"/api/chats/{chat['id']}").json()["model"] == "ollama/gemma4:latest"
    )


def test_send_message_prefers_ollama_when_no_explicit_model(
    client: TestClient, opencode: StubOpencode
) -> None:
    async def mixed_providers() -> list[dict[str, Any]]:
        return [
            {"id": "openai", "name": "OpenAI", "models": [{"id": "o3"}]},
            {
                "id": "ollama",
                "name": "Ollama",
                "models": [{"id": "qwen2.5-coder:7b", "name": "qwen2.5-coder:7b"}],
            },
        ]

    opencode.providers = mixed_providers  # type: ignore[method-assign]
    chat = client.post("/api/chats", json={}).json()
    client.post(f"/api/chats/{chat['id']}/messages", json={"text": "hi"})
    assert opencode.prompts[-1]["model"] == "ollama/qwen2.5-coder:7b"


def test_send_message_e2e_sse_sequence(
    client: TestClient, store: DesktopStore, opencode: StubOpencode
) -> None:
    opencode.script = [
        {"type": "reasoning"},
        {"type": "text", "text": "Hel", "part_id": "prt_1"},
        {"type": "text", "text": "Hello", "part_id": "prt_1"},
        {"type": "complete", "text": "Hello"},
    ]
    chat = client.post(
        "/api/chats", json={"title": "E2E", "model": "ollama/gemma4:latest"}
    ).json()

    frames = _sse_frames(
        client.post(
            f"/api/chats/{chat['id']}/messages",
            json={"text": "ping", "model": "ollama/gemma4:latest"},
        ).text
    )

    assert frames[0]["type"] == "reasoning"
    assert [f["type"] for f in frames] == [
        "reasoning",
        "text",
        "text",
        "complete",
        "end",
    ]
    messages = store.list_messages(chat["id"])
    assert messages[-1]["content"] == "Hello"


def test_send_message_stream_error_still_persists_user_message(
    client: TestClient, store: DesktopStore, opencode: StubOpencode
) -> None:
    opencode.script = [{"type": "error", "message": "provider exploded"}]
    chat = client.post("/api/chats", json={}).json()

    frames = _sse_frames(
        client.post(f"/api/chats/{chat['id']}/messages", json={"text": "hi"}).text
    )
    assert frames[0] == {"type": "error", "message": "provider exploded"}
    assert frames[-1] == {"type": "end"}

    messages = store.list_messages(chat["id"])
    assert [m["role"] for m in messages] == ["user"]  # no empty assistant row


def test_send_message_rejects_non_tool_model(client: TestClient) -> None:
    chat = client.post("/api/chats", json={"model": "ollama/phi:latest"}).json()

    frames = _sse_frames(
        client.post(
            f"/api/chats/{chat['id']}/messages",
            json={"text": "hi", "model": "ollama/phi:latest"},
        ).text
    )
    assert frames[0]["type"] == "error"
    assert "does not support agent tools" in frames[0]["message"]
    assert frames[-1] == {"type": "end"}


def test_send_message_missing_chat_404(client: TestClient) -> None:
    response = client.post("/api/chats/nope/messages", json={"text": "hi"})
    assert response.status_code == 404


def test_send_message_opencode_unavailable_503(
    client: TestClient, opencode: StubOpencode
) -> None:
    opencode.fail_start = True
    chat = client.post("/api/chats", json={}).json()
    response = client.post(f"/api/chats/{chat['id']}/messages", json={"text": "hi"})
    assert response.status_code == 503


def test_abort_is_noop_without_active_generation(client: TestClient) -> None:
    chat = client.post("/api/chats", json={}).json()
    assert client.post(f"/api/chats/{chat['id']}/abort").json() == {"status": "aborted"}


# -- files (workspace-scoped) ---------------------------------------------------


def test_files_list_read_write(client: TestClient, workspace: Path) -> None:
    (workspace / "src").mkdir()
    (workspace / "src" / "app.py").write_text("print('hi')")
    (workspace / ".gitignore-like").write_text("x")
    (workspace / ".git").mkdir()

    listing = client.get("/api/files").json()
    names = [e["name"] for e in listing["entries"]]
    assert "src" in names
    assert ".git" not in names  # .git* filtered

    nested = client.get("/api/files", params={"path": "src"}).json()
    assert nested["entries"][0]["name"] == "app.py"
    assert nested["entries"][0]["is_dir"] is False

    content = client.get("/api/files/content", params={"path": "src/app.py"}).json()
    assert content["content"] == "print('hi')"

    saved = client.put(
        "/api/files/content", json={"path": "new/dir/file.txt", "content": "data"}
    )
    assert saved.status_code == 200
    assert (workspace / "new" / "dir" / "file.txt").read_text() == "data"


def test_files_index_recursive_and_skips_junk(
    client: TestClient, workspace: Path
) -> None:
    (workspace / "src" / "deep").mkdir(parents=True)
    (workspace / "src" / "app.py").write_text("x")
    (workspace / "src" / "deep" / "util.py").write_text("x")
    (workspace / "README.md").write_text("x")
    for junk in (".git", "node_modules", "__pycache__", ".venv"):
        (workspace / junk).mkdir()
        (workspace / junk / "junk.txt").write_text("x")
    (workspace / ".DS_Store").write_bytes(b"\x00")

    payload = client.get("/api/files/index").json()
    assert payload["truncated"] is False
    assert set(payload["files"]) == {
        "README.md",
        "src/app.py",
        "src/deep/util.py",
        "default/default/AGENTS.md",
        "default/default/MEMORY.md",
        "default/default/ontology.ttl",
        "default/default/instances.ttl",
    }


def test_files_index_respects_limit(client: TestClient, workspace: Path) -> None:
    for i in range(5):
        (workspace / f"f{i}.txt").write_text("x")

    payload = client.get("/api/files/index", params={"limit": 3}).json()
    assert len(payload["files"]) == 3
    assert payload["truncated"] is True


def test_files_root_config_visible(client: TestClient, workspace: Path) -> None:
    (workspace / "opencode.json").write_text("{}")
    (workspace / ".env.example").write_text("KEY=\n")
    (workspace / ".hidden").write_text("secret")

    listing = client.get("/api/files").json()
    names = [e["name"] for e in listing["entries"]]
    assert "opencode.json" in names
    assert ".env.example" in names
    assert ".hidden" not in names

    hidden = client.get("/api/files", params={"show_hidden": True}).json()
    hidden_names = [e["name"] for e in hidden["entries"]]
    assert ".hidden" in hidden_names


def test_files_path_traversal_rejected(client: TestClient, tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")

    for path in ("../secret.txt", "../../etc/passwd", "src/../../secret.txt"):
        assert client.get("/api/files", params={"path": path}).status_code == 400
        assert (
            client.get("/api/files/content", params={"path": path}).status_code == 400
        )
        assert (
            client.put(
                "/api/files/content", json={"path": path, "content": "pwn"}
            ).status_code
            == 400
        )
    assert secret.read_text() == "top secret"


def test_files_read_missing_404_and_binary_415(
    client: TestClient, workspace: Path
) -> None:
    assert (
        client.get("/api/files/content", params={"path": "nope.txt"}).status_code == 404
    )
    (workspace / "blob.bin").write_bytes(b"\xff\xfe\x00\x01")
    assert (
        client.get("/api/files/content", params={"path": "blob.bin"}).status_code == 415
    )


def test_files_delete_mkdir_rename(client: TestClient, workspace: Path) -> None:
    assert client.post("/api/files/mkdir", json={"path": "d1"}).status_code == 200
    assert (workspace / "d1").is_dir()

    (workspace / "a.txt").write_text("a")
    renamed = client.post(
        "/api/files/rename", json={"path": "a.txt", "new_path": "b.txt"}
    )
    assert renamed.status_code == 200
    assert (workspace / "b.txt").read_text() == "a"

    assert client.delete("/api/files", params={"path": "b.txt"}).status_code == 200
    assert not (workspace / "b.txt").exists()


def test_files_upload_single_and_nested_dir(
    client: TestClient, workspace: Path
) -> None:
    response = client.post(
        "/api/files/upload",
        data={"dir": "src"},
        files={"files": ("hello.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["uploaded"] == ["src/hello.txt"]
    assert (workspace / "src" / "hello.txt").read_text() == "hello world"


def test_files_upload_multiple(client: TestClient, workspace: Path) -> None:
    response = client.post(
        "/api/files/upload",
        files=[
            ("files", ("a.txt", b"aaa", "text/plain")),
            ("files", ("b.txt", b"bbb", "text/plain")),
        ],
    )
    assert response.status_code == 200
    assert sorted(response.json()["uploaded"]) == ["a.txt", "b.txt"]
    assert (workspace / "a.txt").read_text() == "aaa"
    assert (workspace / "b.txt").read_text() == "bbb"


def test_files_upload_conflict_renames_with_suffix(
    client: TestClient, workspace: Path
) -> None:
    (workspace / "dup.txt").write_text("existing")
    response = client.post(
        "/api/files/upload",
        files={"files": ("dup.txt", b"new", "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["uploaded"] == ["dup_1.txt"]
    assert (workspace / "dup.txt").read_text() == "existing"
    assert (workspace / "dup_1.txt").read_text() == "new"


def test_files_upload_skips_ds_store(client: TestClient, workspace: Path) -> None:
    response = client.post(
        "/api/files/upload",
        files=[
            ("files", (".DS_Store", b"junk", "application/octet-stream")),
            ("files", ("keep.txt", b"ok", "text/plain")),
        ],
    )
    assert response.status_code == 200
    assert response.json()["uploaded"] == ["keep.txt"]
    assert not (workspace / ".DS_Store").exists()


def test_files_upload_path_traversal_rejected(
    client: TestClient, workspace: Path
) -> None:
    response = client.post(
        "/api/files/upload",
        data={"dir": "../escape"},
        files={"files": ("x.txt", b"x", "text/plain")},
    )
    assert response.status_code == 400
    assert not (workspace.parent / "escape").exists()


def test_files_import_local_copies_absolute_paths(
    client: TestClient, workspace: Path, tmp_path: Path
) -> None:
    source = tmp_path / "finder-drop.txt"
    source.write_text("from finder")
    response = client.post(
        "/api/files/import-local",
        json={"paths": [str(source)], "dir": "imports"},
    )
    assert response.status_code == 200
    assert response.json()["uploaded"] == ["imports/finder-drop.txt"]
    assert (workspace / "imports" / "finder-drop.txt").read_text() == "from finder"


def test_files_import_local_conflict_renames(
    client: TestClient, workspace: Path, tmp_path: Path
) -> None:
    (workspace / "same.txt").write_text("old")
    source = tmp_path / "same.txt"
    source.write_text("new")
    response = client.post(
        "/api/files/import-local",
        json={"paths": [str(source)], "dir": ""},
    )
    assert response.status_code == 200
    assert response.json()["uploaded"] == ["same_1.txt"]


def test_files_import_local_spaces_in_filename(
    client: TestClient, workspace: Path, tmp_path: Path
) -> None:
    source = tmp_path / "Data_Governance_Quality_ISO27001 2 (2).html"
    source.write_text("<html><body>governance</body></html>", encoding="utf-8")
    response = client.post(
        "/api/files/import-local",
        json={"paths": [str(source)], "dir": "imports"},
    )
    assert response.status_code == 200
    rel = response.json()["uploaded"][0]
    assert rel == "imports/Data_Governance_Quality_ISO27001 2 (2).html"
    dest = workspace / rel
    assert dest.is_file()
    assert dest.read_text(encoding="utf-8") == "<html><body>governance</body></html>"


def test_send_message_code_includes_open_file_context(
    client: TestClient, opencode: StubOpencode
) -> None:
    chat = client.post("/api/chats", json={"section": "code"}).json()
    client.post(
        f"/api/chats/{chat['id']}/messages",
        json={
            "text": "make the title red",
            "open_file": {
                "path": "templates/slides/starter-deck.html",
                "content": "<html><body>Hello</body></html>",
            },
        },
    )

    prompt = opencode.prompts[-1]["text"]
    assert "templates/slides/starter-deck.html" in prompt
    assert "<html><body>Hello</body></html>" in prompt
    assert "Open file in editor" in prompt
    assert opencode.prompts[-1]["agent"] == "build"
    messages = client.get(f"/api/chats/{chat['id']}/messages").json()
    assert messages[0]["content"] == "make the title red"


# -- model router ---------------------------------------------------------------


def test_router_suggest_returns_ranked_models(client: TestClient) -> None:
    response = client.post(
        "/api/router/suggest",
        json={"text": "refactor this python file", "prefer_local": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent_tags"] == ["code"]
    assert payload["prefer_local"] is True
    suggestions = payload["suggestions"]
    assert len(suggestions) >= 1
    assert suggestions[0]["model_ref"] == "ollama/qwen2.5-coder:7b"
    assert suggestions[0]["hosted_at"] == "local"
    assert "reason" in suggestions[0]


def test_router_suggest_apply_model_and_send_message(
    client: TestClient, opencode: StubOpencode
) -> None:
    """E2E: suggest → apply model on chat → stream message with that model."""
    suggest = client.post(
        "/api/router/suggest",
        json={"text": "refactor this python module", "prefer_local": True},
    ).json()
    top = suggest["suggestions"][0]
    model_ref = top["model_ref"]

    chat = client.post("/api/chats", json={"section": "code"}).json()
    client.patch(f"/api/chats/{chat['id']}", json={"model": model_ref})

    response = client.post(
        f"/api/chats/{chat['id']}/messages",
        json={"text": "implement the feature"},
    )
    assert response.status_code == 200
    frames = _sse_frames(response.text)
    assert any(frame.get("type") == "end" for frame in frames)
    assert opencode.prompts[-1]["model"] == model_ref
    assert client.get(f"/api/chats/{chat['id']}").json()["model"] == model_ref


def test_router_auto_apply_uses_top_suggestion(
    client: TestClient, opencode: StubOpencode, store: DesktopStore
) -> None:
    store.update_settings({"router_auto_apply": "true", "default_model": ""})
    chat = client.post("/api/chats", json={"section": "code"}).json()
    client.post(
        f"/api/chats/{chat['id']}/messages",
        json={"text": "refactor this python file"},
    )
    assert opencode.prompts[-1]["model"] == "ollama/qwen2.5-coder:7b"
    assert (
        client.get(f"/api/chats/{chat['id']}").json()["model"]
        == "ollama/qwen2.5-coder:7b"
    )


def test_integrations_sync_ollama_models_into_instances(
    client: TestClient,
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_probe(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {
            "connected": True,
            "models": [
                {
                    "name": "gemma4:latest",
                    "supports_tools": True,
                }
            ],
            "error": None,
        }

    monkeypatch.setattr("desktop.core.integrations.probe_ollama", fake_probe)
    client.get("/api/integrations")
    instances = (workspace / "default" / "default" / "instances.ttl").read_text(
        encoding="utf-8"
    )
    assert "BEGIN abi-desktop:ollama-models" in instances
    assert 'abi:modelRef "ollama/gemma4:latest"' in instances


# -- sparql -----------------------------------------------------------------------


def test_graph_overview_endpoint(client: TestClient) -> None:
    chat = client.post(
        "/api/chats", json={"title": "KG test", "section": "chat"}
    ).json()
    overview = client.get("/api/graph/overview").json()
    assert overview["meta"]["view"] == "brain"
    assert "nodes" in overview
    assert "edges" in overview
    assert "tables" in overview
    assert len(overview.get("buckets", [])) == 7
    node_ids = {node["id"] for node in overview["nodes"]}
    assert f"chat:{chat['id']}:process" in node_ids
    assert "bfo:anchor:process" not in node_ids
    assert any(node["group"] == "ai_system" for node in overview["nodes"])
    assert any(table["name"] == "chats" for table in overview["tables"])

    full_overview = client.get("/api/graph/overview", params={"view": "full"}).json()
    full_node_ids = {node["id"] for node in full_overview["nodes"]}
    assert "bfo:anchor:process" in full_node_ids


def test_graph_buckets_endpoint(client: TestClient) -> None:
    payload = client.get("/api/graph/buckets").json()
    buckets = payload["buckets"]
    assert len(buckets) == 7
    colors = {bucket["id"]: bucket["color"] for bucket in buckets}
    assert colors["process"] == "#C0392B"
    assert colors["role"] == "#7D3C98"


def test_processes_endpoint_returns_bucket_columns(client: TestClient) -> None:
    chat = client.post(
        "/api/chats", json={"title": "Events row", "section": "chat"}
    ).json()
    payload = client.get("/api/processes").json()
    assert payload["total"] >= 1
    assert payload["limit"] == 50
    assert payload["offset"] == 0
    item = next(row for row in payload["items"] if row["id"] == chat["id"])
    assert item["process_type"] == "chat"
    assert item["process_label"] == "Events row"
    assert item["graph_node_id"] == f"chat:{chat['id']}:process"
    assert set(item["buckets"]) == {
        "process",
        "temporal",
        "material",
        "site",
        "quality",
        "information",
        "role",
    }
    assert item["buckets"]["process"]["status"] == "known"
    assert item["buckets"]["process"]["label"] == "Events row"

    page = client.get("/api/processes", params={"limit": 1, "offset": 0}).json()
    assert len(page["items"]) == 1


def test_tables_endpoint_lists_sqlite_tables_and_rows(client: TestClient) -> None:
    client.post("/api/chats", json={"title": "Table browse", "section": "chat"})
    catalog = client.get("/api/tables").json()
    names = {table["name"] for table in catalog["tables"]}
    assert names == {
        "settings",
        "chats",
        "messages",
        "processes",
        "process_aspects",
        "aspect_entities",
    }
    rows_payload = client.get("/api/tables/chats", params={"limit": 10}).json()
    assert rows_payload["table"] == "chats"
    assert rows_payload["total"] >= 1
    assert rows_payload["rows"]
    assert "title" in rows_payload["rows"][0]

    events_payload = client.get("/api/tables/processes", params={"limit": 10}).json()
    assert events_payload["table"] == "processes"
    assert events_payload["view"] == "events"
    assert events_payload["items"]
    assert "buckets" in events_payload["items"][0]

    alias_payload = client.get("/api/tables/events", params={"limit": 10}).json()
    assert alias_payload["view"] == "events"
    assert alias_payload["items"]

    bad = client.get("/api/tables/not_a_table")
    assert bad.status_code == 400


def test_graph_subclasses_endpoint(client: TestClient) -> None:
    payload = client.get(
        "/api/graph/subclasses",
        params={"iri": "http://ontology.naas.ai/abi/desktop#SectionRoute"},
    ).json()
    assert payload["iri"].endswith("SectionRoute")
    labels = [row["label"] for row in payload["subclasses"]]
    assert any("Chat section route" in label for label in labels)


def test_sparql_endpoint(client: TestClient) -> None:
    result = client.post(
        "/api/sparql", json={"query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"}
    ).json()
    assert result == {"type": "solutions", "variables": ["s"], "rows": []}


def test_sparql_invalid_query_400(client: TestClient) -> None:
    response = client.post("/api/sparql", json={"query": "NOT SPARQL"})
    assert response.status_code == 400
    assert "SPARQL error" in response.json()["detail"]
