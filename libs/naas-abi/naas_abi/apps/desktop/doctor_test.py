"""Tests for the ABI Desktop setup doctor."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from desktop.doctor import (
    COMMON_API_KEYS,
    check_api_keys,
    check_data_dirs,
    check_opencode_binary,
    check_opencode_reachable,
    check_ollama,
    check_workspace,
    run_doctor,
)
from desktop.graph import DesktopGraph
from desktop.harness.adapters.opencode import OpencodeHarnessAdapter
from desktop.server import create_app
from desktop.store import DesktopStore


class StubOpencode:
    def __init__(self, running: bool = True) -> None:
        self._running = running

    def is_running(self) -> bool:
        return self._running


def ollama_transport(connected: bool = True) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if not connected:
            raise httpx.ConnectError("connection refused")
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "llama3"}]})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


# -- individual checks --------------------------------------------------------


class TestCheckOpencodeBinary:
    def test_ok_when_on_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "desktop.doctor.shutil.which", lambda name: "/usr/bin/opencode"
        )
        result = check_opencode_binary(
            {"harness": "opencode", "opencode_bin": "opencode"}
        )
        assert result["status"] == "ok"
        assert result["id"] == "opencode_binary"

    def test_error_when_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("desktop.doctor.shutil.which", lambda name: None)
        result = check_opencode_binary(
            {"harness": "opencode", "opencode_bin": "opencode"}
        )
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()
        assert result["fix"]

    def test_absolute_path_executable(self, tmp_path: Path) -> None:
        binary = tmp_path / "opencode"
        binary.write_text("#!/bin/sh\necho ok\n")
        binary.chmod(0o755)
        result = check_opencode_binary(
            {"harness": "opencode", "opencode_bin": str(binary)}
        )
        assert result["status"] == "ok"

    def test_skipped_for_pi_harness(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("desktop.doctor.shutil.which", lambda name: None)
        result = check_opencode_binary({"harness": "pi", "opencode_bin": "opencode"})
        assert result["status"] == "ok"
        assert "not required" in result["message"].lower()


class TestCheckOpencodeReachable:
    def test_ok_when_running(self) -> None:
        result = check_opencode_reachable(
            {"harness": "opencode"}, StubOpencode(running=True)
        )
        assert result["status"] == "ok"

    def test_error_when_unreachable(self) -> None:
        result = check_opencode_reachable(
            {"harness": "opencode"}, StubOpencode(running=False)
        )
        assert result["status"] == "error"
        assert result["fix"]

    def test_skipped_for_pi_harness(self) -> None:
        result = check_opencode_reachable(
            {"harness": "pi"}, StubOpencode(running=False)
        )
        assert result["status"] == "ok"


class TestCheckApiKeys:
    def test_warn_when_no_env_files(self, tmp_path: Path) -> None:
        result = check_api_keys(str(tmp_path))
        assert result["status"] == "warn"
        assert ".env" in result["message"]
        assert "ollama" in result["message"].lower()

    def test_ok_reports_present_keys_only(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-secret\nANTHROPIC_API_KEY=\n")
        result = check_api_keys(str(tmp_path))
        assert result["status"] == "ok"
        assert "OPENAI_API_KEY" in result["message"]
        assert "sk-secret" not in result["message"]
        assert (
            "ANTHROPIC_API_KEY" not in result["message"]
            or "missing" in result["message"]
        )

    def test_warn_when_files_exist_but_no_keys(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("# no keys here\nFOO=bar\n")
        result = check_api_keys(str(tmp_path))
        assert result["status"] == "warn"
        assert any(k in result["message"] for k in COMMON_API_KEYS[:2])


class TestCheckWorkspace:
    def test_ok_when_writable_git_repo(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".git").mkdir()
        result = check_workspace(str(ws))
        assert result["status"] == "ok"

    def test_error_when_missing(self, tmp_path: Path) -> None:
        result = check_workspace(str(tmp_path / "nope"))
        assert result["status"] == "error"

    def test_error_without_git(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        result = check_workspace(str(ws))
        assert result["status"] == "error"
        assert ".git" in result["message"].lower()

    def test_error_when_not_writable(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".git").mkdir()
        ws.chmod(0o555)
        result = check_workspace(str(ws))
        assert result["status"] == "error"
        assert "writable" in result["message"].lower()


class TestCheckOllama:
    @pytest.mark.asyncio
    async def test_not_configured_when_url_blank(self) -> None:
        result = await check_ollama({"ollama_base_url": ""})
        assert result["status"] == "ok"
        assert "not configured" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_ok_when_reachable(self) -> None:
        result = await check_ollama(
            {"ollama_base_url": "http://localhost:11434"},
            transport=ollama_transport(True),
        )
        assert result["status"] == "ok"
        assert "llama3" in result["message"]

    @pytest.mark.asyncio
    async def test_warn_when_unreachable(self) -> None:
        result = await check_ollama(
            {"ollama_base_url": "http://localhost:11434"},
            transport=ollama_transport(False),
        )
        assert result["status"] == "warn"
        assert result["fix"]


class TestCheckDataDirs:
    def test_ok_when_writable(self, tmp_path: Path) -> None:
        data = tmp_path / "data"
        data.mkdir()
        graph = data / "graph"
        graph.mkdir()
        result = check_data_dirs(data, data / "desktop.db", graph)
        assert result["status"] == "ok"

    def test_error_when_not_writable(self, tmp_path: Path) -> None:
        data = tmp_path / "data"
        data.mkdir()
        graph = data / "graph"
        graph.mkdir()
        data.chmod(0o555)
        result = check_data_dirs(data, data / "desktop.db", graph)
        assert result["status"] == "error"


# -- aggregate + API ----------------------------------------------------------


class TestRunDoctor:
    @pytest.mark.asyncio
    async def test_ready_false_when_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        monkeypatch.setattr("desktop.doctor.shutil.which", lambda name: None)
        report = await run_doctor(
            settings={
                "harness": "opencode",
                "opencode_bin": "opencode",
                "workspace_root": str(ws),
            },
            opencode=StubOpencode(running=False),
            data_dir=tmp_path / "data",
            db_path=tmp_path / "data" / "desktop.db",
            graph_dir=tmp_path / "data" / "graph",
            transport=ollama_transport(False),
        )
        assert report["ready"] is False
        ids = [c["id"] for c in report["checks"]]
        assert "opencode_binary" in ids
        assert "workspace" in ids
        assert any(c["status"] == "error" for c in report["checks"])

    @pytest.mark.asyncio
    async def test_ready_true_when_all_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / ".git").mkdir()
        (ws / ".env").write_text("OPENAI_API_KEY=sk-test\n")
        data = tmp_path / "data"
        data.mkdir()
        graph = data / "graph"
        graph.mkdir()
        monkeypatch.setattr("desktop.doctor.shutil.which", lambda name: "/bin/opencode")
        report = await run_doctor(
            settings={
                "harness": "opencode",
                "opencode_bin": "opencode",
                "workspace_root": str(ws),
                "ollama_base_url": "",
            },
            opencode=StubOpencode(running=True),
            data_dir=data,
            db_path=data / "desktop.db",
            graph_dir=graph,
        )
        assert report["ready"] is True
        assert all(c["status"] != "error" for c in report["checks"])


@pytest.fixture()
def doctor_client(tmp_path: Path) -> TestClient:
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / ".git").mkdir()
    store = DesktopStore(tmp_path / "desktop.db")
    store.update_settings({"workspace_root": str(ws)})
    graph = DesktopGraph(tmp_path / "graph")
    opencode = StubOpencode(running=True)
    harness = OpencodeHarnessAdapter(
        workspace_root=str(ws),
        client=opencode,  # type: ignore[arg-type]
    )
    app = create_app(store=store, graph=graph, harness=harness)
    return TestClient(app)


def test_doctor_api_endpoint(doctor_client: TestClient) -> None:
    payload = doctor_client.get("/api/doctor").json()
    assert "checks" in payload
    assert "ready" in payload
    assert isinstance(payload["checks"], list)
    assert any(c["id"] == "workspace" for c in payload["checks"])
