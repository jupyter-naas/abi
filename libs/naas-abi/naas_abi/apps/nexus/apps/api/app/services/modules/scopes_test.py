"""The listing of module scopes: every module with its agents, apps, workflows,
pipelines and declared actions, with display data; for admins."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.modules import handlers, scopes
from naas_abi.apps.nexus.apps.api.app.services.modules.scopes import Exposed, build
from naas_abi_core.services.iam.module_scopes import module_catalog

DECLARED = module_catalog(
    {
        "resource_types": [{"name": "report", "id": "path", "description": "A report."}],
        "actions": [
            {
                "name": "ExportReport",
                "level": "read",
                "resource_types": ["report"],
                "description": "Export one.",
            }
        ],
    },
    "acme.people",
)

EXPOSED = [
    Exposed("agent", "acme.people", "Recruiter", "Recruiter", "Finds people.", "https://i/r.png"),
    Exposed("agent", "acme.people", "Recruiter", "Recruiter (replica)"),
    Exposed("app", "acme.people", "directory", "Directory", "Who is who.", "📇"),
    Exposed("workflow", "acme.people", "workflow.sync", "workflow.sync", "Syncs."),
    Exposed("pipeline", "acme.people", "pipeline.import", "pipeline.import"),
    Exposed("agent", "naas_abi", "Abi"),
]


def test_a_listing_groups_each_module_s_scopes_with_their_display_data() -> None:
    listed = build(
        EXPOSED, [DECLARED], modules=["naas_abi", "naas_abi_marketplace.applications.github"]
    )
    by_module = {m["module"]: m for m in listed}
    assert list(by_module) == [
        "acme.people",
        "naas_abi",
        "naas_abi_marketplace.applications.github",
    ]

    people = by_module["acme.people"]
    assert people["agents"] == [
        {
            "name": "Recruiter",
            "display_name": "Recruiter",
            "description": "Finds people.",
            "icon": "https://i/r.png",
            "resource": "${scope}/module:agent/acme.people/Recruiter",
            "actions": ["module:UseAgent"],
        }
    ]
    assert people["apps"][0]["resource"] == "${scope}/module:app/acme.people/directory"
    assert people["apps"][0]["actions"] == ["module:OpenApp"]
    assert people["workflows"][0]["actions"] == ["module:RunWorkflow", "module:ReadWorkflowRuns"]
    assert people["pipelines"][0]["actions"] == ["module:RunPipeline", "module:ReadPipelineRuns"]
    assert people["declared"]["service"] == "acme_people"
    assert people["declared"]["actions"] == [
        {
            "action": "acme_people:ExportReport",
            "level": "read",
            "resource_types": ["report"],
            "description": "Export one.",
        }
    ]
    assert people["declared"]["resource_types"][0]["resource"] == "${scope}/acme_people:report/*"

    # naas_abi's own agents are module scopes too; a module with nothing is listed.
    assert [a["name"] for a in by_module["naas_abi"]["agents"]] == ["Abi"]
    empty = by_module["naas_abi_marketplace.applications.github"]
    assert empty["agents"] == [] and empty["declared"] is None


async def _get(user_id: str, path: str):
    app = FastAPI()
    app.include_router(handlers.router, prefix="/api/modules")
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id=user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        return await http.get(path)


@pytest.mark.asyncio
async def test_admins_list_the_module_scopes_of_their_workspace_or_org(team, monkeypatch) -> None:
    async def gathered():
        return build(EXPOSED, [DECLARED])

    monkeypatch.setattr(scopes, "gather", gathered)
    for path in (
        "/api/modules/scopes?workspace_id=ws-1",
        "/api/modules/scopes?organization_id=org-1",
    ):
        for user in ("admin", "owner"):
            response = await _get(user, path)
            assert response.status_code == 200, (user, path)
            assert [m["module"] for m in response.json()["modules"]] == ["acme.people", "naas_abi"]
        for user in ("member", "viewer", "stranger"):
            assert (await _get(user, path)).status_code == 403, (user, path)
    assert (await _get("admin", "/api/modules/scopes")).status_code == 422


@pytest.mark.asyncio
async def test_a_source_that_fails_leaves_its_part_out(monkeypatch) -> None:
    def broken():
        raise RuntimeError("no engine")

    async def remote():
        return [Exposed("agent", "acme.people", "Recruiter")]

    async def nothing():
        return []

    monkeypatch.setattr(scopes, "engine_agents", broken)
    monkeypatch.setattr(scopes, "remote_agents", remote)
    monkeypatch.setattr(scopes, "apps", nothing)
    monkeypatch.setattr(scopes, "workflows", nothing)
    monkeypatch.setattr(scopes, "declared_catalogs", broken)
    monkeypatch.setattr(scopes, "engine_modules", lambda: [])
    listed = await scopes.gather()
    assert [(m["module"], [a["name"] for a in m["agents"]]) for m in listed] == [
        ("acme.people", ["Recruiter"])
    ]


def test_what_a_caller_may_use_is_each_module_with_its_usable_items() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope

    listed = build(EXPOSED, [DECLARED], modules=["naas_abi_marketplace.applications.github"])
    every = scopes.item_scopes(listed)
    counts = {"agents": 1, "apps": 1, "workflows": 1, "pipelines": 1}
    # Everything usable; a module with nothing is left out.
    assert scopes.counted(listed, set(every)) == [
        {"module": "acme.people", **counts},
        {"module": "naas_abi", "agents": 1, "apps": 0, "workflows": 0, "pipelines": 0},
    ]
    one_app = {
        ModuleScope("app", "acme.people", "directory"),
        *(s for s in every if s.type == "agent"),
    }
    assert scopes.counted(listed, one_app) == [
        {"module": "acme.people", "agents": 1, "apps": 1, "workflows": 0, "pipelines": 0},
        {"module": "naas_abi", "agents": 1, "apps": 0, "workflows": 0, "pipelines": 0},
    ]
    assert scopes.counted(listed, set()) == []


@pytest.mark.asyncio
async def test_discovery_down_names_the_apps_as_unavailable(monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary import (
        apps__primary_adapter__FastAPI as apps_api,
    )

    async def discovery_down(*, strict=False):
        raise RuntimeError("no NATS")

    async def nothing():
        return []

    monkeypatch.setattr(apps_api, "_scan_apps_catalog", lambda: ())
    monkeypatch.setattr(apps_api, "_remote_apps_catalog", discovery_down)
    for name in ("engine_agents", "remote_agents", "workflows"):
        monkeypatch.setattr(scopes, name, nothing)
    monkeypatch.setattr(scopes, "declared_catalogs", lambda: [])
    monkeypatch.setattr(scopes, "engine_modules", lambda: [])
    unavailable: set[str] = set()
    assert await scopes.gather(unavailable) == []
    assert unavailable == {"apps"}
