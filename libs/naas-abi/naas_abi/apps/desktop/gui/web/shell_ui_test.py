"""Shell layout conventions for ABI Desktop web UI."""

from __future__ import annotations

from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent


def _read(name: str) -> str:
    return (WEB_DIR / name).read_text(encoding="utf-8")


def test_rail_logo_only_workspace_switcher() -> None:
    html = _read("index.html")
    assert 'id="workspace-switcher"' in html
    assert 'id="workspace-logo"' in html
    assert 'id="workspace-name"' not in html
    assert "workspace-switcher-label" not in html
    assert "workspace-chevron" not in html


def test_status_bar_shows_workspace_name() -> None:
    html = _read("index.html")
    assert 'id="status-workspace"' in html
    assert 'id="status-git"' in html
    assert html.index('id="status-workspace"') < html.index('id="status-git"')


def test_workspace_menu_nexus_style() -> None:
    html = _read("index.html")
    assert 'id="workspace-menu"' in html
    assert 'class="workspace-menu glass-card' in html
    assert "workspace-menu-heading" in html
    assert "Workspaces" in html
    assert 'id="workspace-menu-open-folder"' in html
    assert "workspace-menu-path" not in html


def test_app_shell_status_bar_layout() -> None:
    html = _read("index.html")
    assert 'id="app-shell"' in html
    assert 'id="status-bar"' in html
    assert html.index('id="app-shell"') < html.index('id="status-bar"')


def test_workspace_switcher_js_uses_status_not_rail_name() -> None:
    js = _read("app.js")
    assert "status-workspace" in js
    assert "workspace-name" not in js
    assert "workspace-menu-path" not in js
    assert "rect.right + 8" in js


def test_workspace_switcher_css_logo_button() -> None:
    css = _read("style.css")
    assert ".glass-card" in css
    assert ".workspace-switcher" in css
    assert "workspace-switcher-label" not in css
    assert "#workspace-name" not in css
