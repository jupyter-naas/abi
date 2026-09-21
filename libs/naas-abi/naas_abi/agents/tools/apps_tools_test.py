from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi.agents.feature.context import nexus_feature_context
from naas_abi.agents.tools import apps_tools as tools_module
from naas_abi.apps.nexus.apps.api.app.services.apps.port import (
    AppConfigRecord,
    AppInfo,
)
from naas_abi_core.services.agent.context import agent_user_id, agent_workspace_id

WSR = "acme.module:wsr"
DOCS = "acme.module:docs"


def _app(app_name: str, **extra: Any) -> AppInfo:
    return AppInfo(
        module_path="acme.module",
        module_name="module",
        app_name=app_name,
        app_id=f"acme.module:{app_name}",
        category="application",
        name=app_name.upper(),
        url=f"/app-html/acme/module/{app_name}/index.html",
        installed=True,
        **extra,
    )


class _FakeAppsService:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, str, bool | None]] = []

    async def upsert_app_config(self, workspace_id, app_id, updates):
        self.upserts.append((workspace_id, app_id, updates.enabled))
        now = datetime(2026, 9, 10, tzinfo=UTC)
        return AppConfigRecord(
            id="cfg-1",
            workspace_id=workspace_id,
            app_id=app_id,
            enabled=bool(updates.enabled),
            created_at=now,
            updated_at=now,
        )


@pytest.fixture
def apps(monkeypatch) -> dict[str, Any]:
    service = _FakeAppsService()
    catalog = [_app("wsr", demo_login="demo", demo_password="s3cret"), _app("docs")]
    external = [
        SimpleNamespace(name="Status", url="https://status.example.com", description="")
    ]

    async def _with_db(fn):
        return await fn(object())

    async def _enable_state(db, user_id, workspace_id):
        return {DOCS: False}, {WSR, DOCS}

    monkeypatch.setattr(tools_module, "_catalog", lambda: catalog)
    monkeypatch.setattr(tools_module, "_external_apps", lambda: external)
    monkeypatch.setattr(tools_module, "_with_db", _with_db)
    monkeypatch.setattr(tools_module, "_enable_state", _enable_state)
    monkeypatch.setattr(tools_module, "_apps_service", lambda db: service)

    tokens = [
        agent_user_id.set("user-1"),
        agent_workspace_id.set("ws-1"),
        nexus_feature_context.set(None),
    ]
    yield {"service": service, "tools": {t.name: t for t in tools_module.apps_tools()}}
    agent_user_id.reset(tokens[0])
    agent_workspace_id.reset(tokens[1])
    nexus_feature_context.reset(tokens[2])


def _open(app_id: str) -> None:
    nexus_feature_context.set(
        {"key": "apps", "resource": {"kind": "app", "id": app_id, "label": "WSR"}}
    )


def test_list_resolves_db_row_then_seed_and_adds_external(apps) -> None:
    out = apps["tools"]["list_workspace_apps"].invoke({})
    rows = {row["app_id"]: row for row in out["apps"]}

    assert rows[WSR]["enabled"] is True  # seed only
    assert rows[DOCS]["enabled"] is False  # DB row wins over seed
    assert rows[WSR]["embed"] == "bundled"
    assert rows["https://status.example.com"]["source"] == "external"
    assert out["open_app_id"] is None


def test_list_can_match_the_apps_page(apps) -> None:
    out = apps["tools"]["list_workspace_apps"].invoke({"include_disabled": False})
    ids = [row["app_id"] for row in out["apps"]]
    assert DOCS not in ids
    assert WSR in ids


def test_get_app_defaults_to_the_open_app_and_hides_the_password(apps) -> None:
    _open(WSR)
    out = apps["tools"]["get_app"].invoke({})

    assert out["app_id"] == WSR
    assert out["has_demo_login"] is True
    assert "s3cret" not in str(out)
    assert out["open_in_nexus"] == "/workspace/ws-1/apps?open=acme.module%3Awsr"


def test_get_app_without_open_app_asks_for_an_id(apps) -> None:
    out = apps["tools"]["get_app"].invoke({})
    assert "No app is open" in out["error"]


def test_get_app_rejects_unknown_ids(apps) -> None:
    out = apps["tools"]["get_app"].invoke({"app_id": "nope:app"})
    assert "Unknown app_id" in out["error"]


def test_set_app_enabled_toggles_the_open_app(apps) -> None:
    _open(DOCS)
    out = apps["tools"]["set_app_enabled"].invoke({"enabled": True})

    assert apps["service"].upserts == [("ws-1", DOCS, True)]
    assert out["enabled"] is True
    assert out["name"] == "DOCS"


def test_set_app_enabled_refuses_external_shortcuts(apps) -> None:
    out = apps["tools"]["set_app_enabled"].invoke(
        {"enabled": False, "app_id": "https://status.example.com"}
    )
    assert "tenant.apps" in out["error"]
    assert apps["service"].upserts == []


def test_tools_need_a_signed_in_user(apps) -> None:
    agent_user_id.set(None)
    out = apps["tools"]["list_workspace_apps"].invoke({})
    assert "No authenticated user" in out["error"]


def test_membership_refusal_is_reported(apps, monkeypatch) -> None:
    async def _denied(db, user_id, workspace_id):
        return {"error": "You do not have access to this workspace."}

    monkeypatch.setattr(tools_module, "_enable_state", _denied)
    _open(DOCS)
    out = apps["tools"]["set_app_enabled"].invoke({"enabled": True})

    assert "do not have access" in out["error"]
    assert apps["service"].upserts == []
