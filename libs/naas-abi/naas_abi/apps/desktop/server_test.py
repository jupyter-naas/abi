"""API tests for the ABI Desktop FastAPI backend.

Everything runs against tmp_path-backed store/graph/workspace and a stub
opencode client injected through ``create_app`` — no real opencode binary,
no network, nothing under ``~/.abi-desktop``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient

from desktop.graph import ABID, DesktopGraph
from desktop.harness.adapters.opencode import OpencodeHarnessAdapter
from desktop.opencode_client import OpencodeUnavailableError
from desktop.server import create_app
from desktop.store import DesktopStore


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
    assert payload["graph"] == {"triples": 0}
    assert payload["workspace_root"] == str(workspace)
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


def test_send_message_reuses_session_and_code_agent(
    client: TestClient, opencode: StubOpencode
) -> None:
    chat = client.post("/api/chats", json={"section": "code"}).json()
    client.post(f"/api/chats/{chat['id']}/messages", json={"text": "one"})
    client.post(f"/api/chats/{chat['id']}/messages", json={"text": "two"})

    assert [p["session_id"] for p in opencode.prompts] == ["ses_1", "ses_1"]
    assert all(p["agent"] == "build" for p in opencode.prompts)


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
    assert client.get(f"/api/chats/{chat['id']}").json()["model"] == "ollama/gemma4:latest"


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
    assert [f["type"] for f in frames] == ["reasoning", "text", "text", "complete", "end"]
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
    chat = client.post(
        "/api/chats", json={"model": "ollama/phi:latest"}
    ).json()

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
    assert payload["files"] == ["README.md", "src/app.py", "src/deep/util.py"]


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


# -- sparql -----------------------------------------------------------------------


def test_sparql_endpoint(client: TestClient) -> None:
    result = client.post(
        "/api/sparql", json={"query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"}
    ).json()
    assert result == {"type": "solutions", "variables": ["s"], "rows": []}


def test_sparql_invalid_query_400(client: TestClient) -> None:
    response = client.post("/api/sparql", json={"query": "NOT SPARQL"})
    assert response.status_code == 400
    assert "SPARQL error" in response.json()["detail"]
