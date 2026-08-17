"""Tests for the manifest ``agent_path`` / ``agent_class`` → agent registry join."""

from __future__ import annotations

from pathlib import Path

import pytest
from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary import (
    apps__primary_adapter__FastAPI as adapter,
)

REGISTRY = {
    "osint.agents.OsintAgent/OsintAgent": object,
    "naas_abi.agents.AbiAgent/AbiAgent": object,
    "report.agents.ReportAgent/ReportAgent": object,
}


@pytest.fixture(autouse=True)
def _clear_resolution_cache():
    adapter._resolve_agent_class_name.cache_clear()
    yield
    adapter._resolve_agent_class_name.cache_clear()


@pytest.fixture
def registry(monkeypatch):
    """Stand in for the live agent class registry."""
    import naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI as agents_adapter  # noqa: E501

    monkeypatch.setattr(agents_adapter, "_get_agent_class_registry", lambda: REGISTRY)
    return REGISTRY


@pytest.mark.parametrize(
    "agent_path,expected",
    [
        ("src/osint/agents/OsintAgent.py", "osint"),
        ("osint/agents/OsintAgent.py", "osint"),
        ("src/report/agents/sub/ReportAgent.py", "sub"),
        ("OsintAgent.py", None),
        ("", None),
        (None, None),
    ],
)
def test_agent_module_hint(agent_path, expected):
    assert adapter._agent_module_hint(agent_path) == expected


@pytest.mark.parametrize(
    "agent_path,expected",
    [
        ("src/osint/agents/OsintAgent.py", "OsintAgent"),
        ("src/osint/agents/OsintAgent", None),
        (None, None),
    ],
)
def test_agent_class_from_path(agent_path, expected):
    assert adapter._agent_class_from_path(agent_path) == expected


def test_resolve_agent_class_name_from_class(registry):
    assert (
        adapter._resolve_agent_class_name("src/osint/agents/OsintAgent.py", "OsintAgent")
        == "osint.agents.OsintAgent/OsintAgent"
    )


def test_resolve_agent_class_name_falls_back_to_path_stem(registry):
    assert (
        adapter._resolve_agent_class_name("src/osint/agents/OsintAgent.py", None)
        == "osint.agents.OsintAgent/OsintAgent"
    )


def test_resolve_agent_class_name_without_path(registry):
    assert (
        adapter._resolve_agent_class_name(None, "OsintAgent")
        == "osint.agents.OsintAgent/OsintAgent"
    )


def test_resolve_agent_class_name_breaks_ties_with_the_path(monkeypatch):
    import naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI as agents_adapter  # noqa: E501

    ambiguous = {
        "demo.agents.OsintAgent/OsintAgent": object,
        "osint.agents.OsintAgent/OsintAgent": object,
    }
    monkeypatch.setattr(agents_adapter, "_get_agent_class_registry", lambda: ambiguous)
    assert (
        adapter._resolve_agent_class_name("src/osint/agents/OsintAgent.py", "OsintAgent")
        == "osint.agents.OsintAgent/OsintAgent"
    )


def test_resolve_agent_class_name_returns_none_for_unknown_agent(registry):
    assert adapter._resolve_agent_class_name(None, "NotLoadedAgent") is None


def test_resolve_agent_class_name_returns_none_when_unset(registry):
    assert adapter._resolve_agent_class_name(None, None) is None


def test_build_app_info_reads_agent_fields(tmp_path: Path):
    app_dir = tmp_path / "osint"
    app_dir.mkdir()
    info = adapter._build_app_info(
        "osint",
        app_dir,
        {
            "name": "OSINT Orchestration Hub",
            "category": "private",
            "url": "/app-html/osint/osint/index.html",
            "agent_path": "src/osint/agents/OsintAgent.py",
            "agent_class": "OsintAgent",
        },
    )
    assert info.agent_path == "src/osint/agents/OsintAgent.py"
    assert info.agent_class == "OsintAgent"
    # Resolution happens per request, not in the cached scan.
    assert info.agent_class_name is None


def test_build_app_info_without_agent_fields(tmp_path: Path):
    app_dir = tmp_path / "dashboard"
    app_dir.mkdir()
    info = adapter._build_app_info("some.module", app_dir, {"name": "Dashboard"})
    assert info.agent_path is None
    assert info.agent_class is None
    assert info.agent_class_name is None
