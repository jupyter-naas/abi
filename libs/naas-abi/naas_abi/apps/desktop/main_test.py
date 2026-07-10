"""Tests for desktop.main CLI and browser-only dev mode."""

from __future__ import annotations

import pytest

from desktop.main import _parse_args, browser_only_mode


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
