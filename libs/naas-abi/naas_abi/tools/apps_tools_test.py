from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi_core.services.agent.context import agent_user_id, agent_workspace_id

from naas_abi.agents.feature.context import nexus_feature_context
from naas_abi.apps.nexus.apps.api.app.services.apps.port import AppInfo
from naas_abi.tools import apps_tools as tools_module

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


@pytest.fixture
def apps(monkeypatch) -> dict[str, Any]:
    catalog = [_app("wsr", demo_login="demo", demo_password="s3cret"), _app("docs")]
    external = [
        SimpleNamespace(name="Status", url="https://status.example.com", description="")
    ]
    # The apps IAM lets the user open (``module:OpenApp``).
    allowed = {"ids": {WSR}}

    async def _with_db(fn):
        return await fn(object())

    async def _usable(db, user_id, workspace_id, found):
        return [app for app in found if app.app_id in allowed["ids"]]

    monkeypatch.setattr(tools_module, "_catalog", lambda: catalog)
    monkeypatch.setattr(tools_module, "_external_apps", lambda: external)
    monkeypatch.setattr(tools_module, "_with_db", _with_db)
    monkeypatch.setattr(tools_module, "_usable", _usable)

    tokens = [
        agent_user_id.set("user-1"),
        agent_workspace_id.set("ws-1"),
        nexus_feature_context.set(None),
    ]
    yield {"allowed": allowed, "tools": {t.name: t for t in tools_module.apps_tools()}}
    agent_user_id.reset(tokens[0])
    agent_workspace_id.reset(tokens[1])
    nexus_feature_context.reset(tokens[2])


def _open(app_id: str) -> None:
    nexus_feature_context.set(
        {"key": "apps", "resource": {"kind": "app", "id": app_id, "label": "WSR"}}
    )


def test_list_is_what_the_user_may_open_and_the_external_shortcuts(apps) -> None:
    out = apps["tools"]["list_workspace_apps"].invoke({})
    rows = {row["app_id"]: row for row in out["apps"]}

    assert set(rows) == {WSR, "https://status.example.com"}
    assert rows[WSR]["embed"] == "bundled"
    assert "enabled" not in rows[WSR]
    assert rows["https://status.example.com"]["source"] == "external"
    assert out["open_app_id"] is None


def test_the_tools_switch_nothing(apps) -> None:
    assert set(apps["tools"]) == {"list_workspace_apps", "get_app"}


def test_get_app_defaults_to_the_open_app_and_hides_the_password(apps) -> None:
    _open(WSR)
    out = apps["tools"]["get_app"].invoke({})

    assert out["app_id"] == WSR
    assert out["has_demo_login"] is True
    assert "s3cret" not in str(out)
    assert out["open_in_nexus"] == "/workspace/ws-1/apps?open=acme.module%3Awsr"


def test_get_app_of_an_app_the_user_may_not_open_is_refused(apps) -> None:
    out = apps["tools"]["get_app"].invoke({"app_id": DOCS})
    assert "may not open" in out["error"]


def test_get_app_without_open_app_asks_for_an_id(apps) -> None:
    out = apps["tools"]["get_app"].invoke({})
    assert "No app is open" in out["error"]


def test_get_app_rejects_unknown_ids(apps) -> None:
    out = apps["tools"]["get_app"].invoke({"app_id": "nope:app"})
    assert "Unknown app_id" in out["error"]


def test_tools_need_a_signed_in_user(apps) -> None:
    agent_user_id.set(None)
    out = apps["tools"]["list_workspace_apps"].invoke({})
    assert "No authenticated user" in out["error"]


def test_membership_refusal_is_reported(apps, monkeypatch) -> None:
    async def _denied(db, user_id, workspace_id, found):
        return {"error": "You do not have access to this workspace."}

    monkeypatch.setattr(tools_module, "_usable", _denied)
    out = apps["tools"]["list_workspace_apps"].invoke({})

    assert "do not have access" in out["error"]


@pytest.mark.asyncio
async def test_the_apps_listed_are_those_iam_lets_the_user_open(monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
    from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam

    class Workspaces:
        async def require_workspace_access(self, *, user_id, workspace_id):
            return None

    monkeypatch.setattr(tools_module, "_workspace_service", lambda db: Workspaces())
    team = NexusIam()
    scope = team.workspace("org-1", "ws-1")
    for role in ("admin", "member"):
        team.grant(role, role, scope)
    wsr, docs = _app("wsr"), _app("docs")
    with team.installed():
        # No role holds an app: an admin with no policy opens none.
        assert await tools_module._usable(object(), "admin", "ws-1", [wsr, docs]) == []
        team.allow_scope("member", ModuleScope("app", "acme.module", "wsr"), scope)
        assert await tools_module._usable(object(), "member", "ws-1", [wsr, docs]) == [
            wsr
        ]
