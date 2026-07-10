"""Tests for desktop.main CLI, port resolution, and browser-only dev mode."""

from __future__ import annotations

import os
import socket
from typing import Iterator

import pytest

from desktop.main import (
    _parse_args,
    _pid_on_port,
    _port_available,
    browser_only_mode,
    reload_enabled,
    resolve_server_port,
)


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


def test_resolve_server_port_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ABI_DESKTOP_PORT", raising=False)
    assert resolve_server_port() == 54242


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


def test_resolve_server_port_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ABI_DESKTOP_PORT", raising=False)
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 54242))
    try:
        port = resolve_server_port(allow_fallback=True)
        assert port == 54243
    finally:
        blocker.close()


def test_resolve_server_port_in_use_exits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ABI_DESKTOP_PORT", "54242")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 54242))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock2:
            sock2.bind(("127.0.0.1", 54243))
            with pytest.raises(SystemExit) as exc:
                resolve_server_port(allow_fallback=True)
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "54242 in use" in err
    assert "ABI_DESKTOP_PORT" in err


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
