"""Tests for desktop.main CLI, port resolution, and browser-only dev mode."""

from __future__ import annotations

import os
import socket
from typing import Iterator

import pytest

from desktop.config import desktop_config
from desktop.main import (
    UVICORN_FACTORY_TARGET,
    _parse_args,
    _pid_on_port,
    _port_available,
    browser_only_mode,
    reload_enabled,
    resolve_server_port,
)


@pytest.fixture
def ephemeral_default_port(monkeypatch: pytest.MonkeyPatch) -> int:
    """Use a free port in tests so 54242 conflicts with a running app never flake."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    monkeypatch.setattr(desktop_config, "DEFAULT_SERVER_PORT", port)
    monkeypatch.setattr("desktop.main.DEFAULT_SERVER_PORT", port)
    return port


def test_browser_only_flag() -> None:
    assert browser_only_mode(["--browser-only"]) is True
    assert browser_only_mode([]) is False


def test_browser_only_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABI_DESKTOP_BROWSER", "1")
    assert browser_only_mode([]) is True


def test_no_open_browser_flag() -> None:
    args = _parse_args(["--browser-only", "--no-open-browser"])
    assert args.browser_only is True
    assert args.no_open_browser is True


def test_reload_flag() -> None:
    assert reload_enabled(["--reload"]) is True
    assert reload_enabled([]) is False


def test_reload_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABI_DESKTOP_RELOAD", "1")
    assert reload_enabled([]) is True


def test_uvicorn_factory_target() -> None:
    assert UVICORN_FACTORY_TARGET == "desktop.api.server:create_app"


def test_resolve_server_port_default(
    monkeypatch: pytest.MonkeyPatch, ephemeral_default_port: int
) -> None:
    monkeypatch.delenv("ABI_DESKTOP_PORT", raising=False)
    assert resolve_server_port() == ephemeral_default_port


def test_resolve_server_port_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABI_DESKTOP_PORT", "9999")
    assert resolve_server_port() == 9999


def test_resolve_server_port_invalid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABI_DESKTOP_PORT", "not-a-port")
    with pytest.raises(SystemExit):
        resolve_server_port()


def test_port_available_on_free_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    assert _port_available(port) is True


def test_port_available_when_bound() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
        assert _port_available(port) is False


def test_resolve_server_port_fallback(
    monkeypatch: pytest.MonkeyPatch, ephemeral_default_port: int
) -> None:
    monkeypatch.delenv("ABI_DESKTOP_PORT", raising=False)
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", ephemeral_default_port))
    try:
        port = resolve_server_port(allow_fallback=True)
        assert port == ephemeral_default_port + 1
    finally:
        blocker.close()


def test_resolve_server_port_in_use_exits(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    ephemeral_default_port: int,
) -> None:
    port = ephemeral_default_port
    monkeypatch.setenv("ABI_DESKTOP_PORT", str(port))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock2:
            sock2.bind(("127.0.0.1", port + 1))
            with pytest.raises(SystemExit) as exc:
                resolve_server_port(allow_fallback=True)
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert f"{port} in use" in err
    assert "ABI_DESKTOP_PORT" in err


def test_resolve_server_port_env_already_running_abi(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    ephemeral_default_port: int,
) -> None:
    """When ABI_DESKTOP_PORT is set and our app is healthy, exit 0 (idempotent)."""
    from unittest.mock import patch

    port = ephemeral_default_port
    monkeypatch.setenv("ABI_DESKTOP_PORT", str(port))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))
        with patch("desktop.main._is_abi_desktop_on_port", return_value=True):
            with patch("desktop.main._read_server_url", return_value=f"http://127.0.0.1:{port}"):
                with pytest.raises(SystemExit) as exc:
                    resolve_server_port(allow_fallback=False)
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "already running" in out


@pytest.fixture
def bound_port() -> Iterator[int]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        yield int(sock.getsockname()[1])


def test_pid_on_port_when_bound(bound_port: int) -> None:
    pid = _pid_on_port(bound_port)
    assert pid == os.getpid()


def test_pid_on_port_when_free() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = int(sock.getsockname()[1])
    assert _pid_on_port(port) is None
