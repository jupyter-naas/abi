from __future__ import annotations

import httpx
import pytest
from click.testing import CliRunner

from naas_abi_platform import cli


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/api/platform/storage/ls":
        return httpx.Response(200, json={"items": ["a.txt", "dir/b.bin"]})
    if path == "/api/platform/storage/download":
        return httpx.Response(200, content=b"remote-bytes")
    if path == "/api/platform/storage/upload":
        # echo back what the server would return; body was streamed here
        assert request.content == b"local-bytes"
        return httpx.Response(200, json={"ok": True, "path": request.url.params.get("path")})
    return httpx.Response(404, json={"detail": "not found"})


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    monkeypatch.setenv("ABI_API_BASE", "http://abi:9879")
    monkeypatch.setenv("ABI_TOKEN", "tok")
    monkeypatch.setattr(cli, "_TEST_TRANSPORT", httpx.MockTransport(_handler))
    return CliRunner()


def test_ls(runner: CliRunner) -> None:
    res = runner.invoke(cli.main, ["storage", "ls"])
    assert res.exit_code == 0, res.output
    assert "a.txt" in res.output
    assert "dir/b.bin" in res.output


def test_cp_download(runner: CliRunner, tmp_path) -> None:
    dst = tmp_path / "out.bin"
    res = runner.invoke(cli.main, ["storage", "cp", "remote:x.bin", str(dst)])
    assert res.exit_code == 0, res.output
    assert dst.read_bytes() == b"remote-bytes"


def test_cp_upload(runner: CliRunner, tmp_path) -> None:
    src = tmp_path / "in.bin"
    src.write_bytes(b"local-bytes")
    res = runner.invoke(cli.main, ["storage", "cp", str(src), "remote:up/in.bin"])
    assert res.exit_code == 0, res.output
    assert "uploaded" in res.output


def test_cp_requires_exactly_one_remote(runner: CliRunner) -> None:
    res = runner.invoke(cli.main, ["storage", "cp", "a.txt", "b.txt"])
    assert res.exit_code != 0
    assert "remote:" in res.output


def test_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ABI_API_BASE", raising=False)
    monkeypatch.delenv("ABI_TOKEN", raising=False)
    res = CliRunner().invoke(cli.main, ["storage", "ls"])
    assert res.exit_code != 0
    assert "ABI_API_BASE" in res.output
