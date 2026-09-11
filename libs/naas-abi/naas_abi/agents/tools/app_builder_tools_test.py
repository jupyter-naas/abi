from __future__ import annotations

import contextvars
from pathlib import Path
from typing import Any

import pytest
from naas_abi.agents.feature.context import bind_feature_context
from naas_abi.agents.tools import app_builder_tools as tools_module
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.object_storage import (
    AppDraftStoreObjectStorage,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.source_control import (
    AppProjectRepositoryGit,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import AppAuthor
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.service import (
    AppProjectsService,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)

WS = "ws-1"


@pytest.fixture
def tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    sc = SourceControlService(InMemoryAdapter())
    sc.ensure_repo(owner="abi", name="monorepo")
    service = AppProjectsService(
        repository=AppProjectRepositoryGit(sc, "abi/monorepo"),
        drafts=AppDraftStoreObjectStorage(
            ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
        ),
    )
    author = AppAuthor("u-1", "Alice", "alice@example.com")
    monkeypatch.setattr(tools_module, "_caller", lambda: (WS, "u-1", author))
    monkeypatch.setattr(tools_module, "_service", lambda: service)
    return {t.name: t for t in tools_module.app_builder_tools()}


def _in_editor(slug: str, errors: list[str] | None = None) -> None:
    bind_feature_context(
        {
            "feature": {
                "key": "apps",
                "resource": {"kind": "app_project", "id": slug},
                **({"errors": errors} if errors else {}),
            }
        }
    )


def test_builder_flow_defaults_to_the_open_project(tools: dict[str, Any]) -> None:
    def _run() -> None:
        created = tools["create_app_project"].invoke({"title": "Budget Tracker"})
        assert (
            created["created"]
            and created["editor"] == f"/workspace/{WS}/apps/p/budget-tracker"
        )
        _in_editor("budget-tracker")

        listed = tools["list_app_files"].invoke({})
        assert {f["path"] for f in listed["files"]} >= {"index.html", "styles.css"}

        write = tools["write_app_file"].invoke(
            {"path": "js/chart.js", "content": "export {}"}
        )
        assert write == {"written": "js/chart.js", "size": 9, "saved": False}
        assert (
            tools["read_app_file"].invoke({"path": "js/chart.js"})["content"]
            == "export {}"
        )

        saved = tools["save_app_project"].invoke({"message": "feat(apps): chart"})
        assert saved["saved"] and saved["message"] == "feat(apps): chart"
        assert tools["save_app_project"].invoke({})["saved"] is False

    contextvars.copy_context().run(_run)


def test_replace_needs_exactly_one_match(tools: dict[str, Any]) -> None:
    def _run() -> None:
        tools["create_app_project"].invoke({"title": "Demo"})
        _in_editor("demo")
        tools["write_app_file"].invoke({"path": "a.css", "content": "h1{} h1{}"})
        twice = tools["replace_in_app_file"].invoke(
            {"path": "a.css", "old": "h1{}", "new": "h2{}"}
        )
        assert "2 times" in twice["error"]
        once = tools["replace_in_app_file"].invoke(
            {"path": "a.css", "old": "h1{} h1{}", "new": "h1{color:red}"}
        )
        assert once["written"] == "a.css"
        assert (
            tools["read_app_file"].invoke({"path": "a.css"})["content"]
            == "h1{color:red}"
        )

    contextvars.copy_context().run(_run)


def test_check_reports_the_preview_errors(tools: dict[str, Any]) -> None:
    def _run() -> None:
        tools["create_app_project"].invoke({"title": "Demo"})
        _in_editor("demo", errors=["ReferenceError: chart is not defined (app.js:4)"])
        result = tools["check_app"].invoke({})
        assert result["preview_errors"] == [
            "ReferenceError: chart is not defined (app.js:4)"
        ]
        assert result["ok"] is False

    contextvars.copy_context().run(_run)


def test_rules_come_back_as_tool_errors(tools: dict[str, Any]) -> None:
    def _run() -> None:
        bind_feature_context({})
        assert "No app project is open" in tools["list_app_files"].invoke({})["error"]
        tools["create_app_project"].invoke({"title": "Demo"})
        _in_editor("demo")
        refused = tools["write_app_file"].invoke({"path": ".env", "content": "KEY=1"})
        assert "Dotfiles" in refused["error"]
        submit = tools["submit_app_project"].invoke({})
        assert "not configured" in submit["error"]

    contextvars.copy_context().run(_run)
