from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi import WorkspaceSeedConfig
from naas_abi.apps.nexus.apps.api.app.services.chat.service import ChatService
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
from naas_abi.apps.nexus.apps.api.app.services.skills.adapters.secondary import (
    module_catalog as catalog_adapter,
)
from naas_abi.apps.nexus.apps.api.app.services.skills.service import (
    SkillPermissionError,
    SkillService,
    module_skill_id,
)
from naas_abi_core.module.ModuleSkillLoader import ModuleSkillLoader


def _module(root, name, slug="weekly"):
    path = root / name / "skills" / slug / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        f"---\nname: {name} report\ndescription: Weekly report\nwhen_to_use: Weekly request\n---\n\n{name} private procedure"
    )
    (path.parent / "reference.md").write_text(f"{name} reference")
    return SimpleNamespace(skills=ModuleSkillLoader.load_skills(str(root / name)))


def _context():
    return RequestContext(
        token_data=TokenData(user_id="alice", scopes={"*"}, is_authenticated=True)
    )


def test_workspace_skill_config_defaults_and_validation():
    for value in ({}, {"skills": None}, {"skills": []}):
        config = WorkspaceSeedConfig(name="Workspace", slug="workspace", **value)
        assert not config.skills
    module_config = WorkspaceSeedConfig(
        name="Workspace", slug="workspace", skills=["example:weekly"]
    )
    from naas_abi.apps.nexus.apps.api.app.core.config import WorkspaceSeedConfig as RuntimeConfig

    assert RuntimeConfig.model_validate(module_config.model_dump()).skills == ["example:weekly"]


@pytest.mark.asyncio
async def test_module_catalog_follows_config_and_authorizes_direct_reads(tmp_path, monkeypatch):
    modules = {"example": _module(tmp_path, "example"), "other": _module(tmp_path, "other")}
    alpha = SimpleNamespace(slug="alpha", skills=["example:weekly"])
    beta = SimpleNamespace(slug="beta", skills=["other:weekly"])
    settings = SimpleNamespace(
        organizations=[SimpleNamespace(slug="org", workspaces=[alpha, beta])]
    )
    monkeypatch.setattr(catalog_adapter, "live_settings", lambda: settings)
    db = AsyncMock()

    def execute(query):
        ws = query.compile().params["id_1"]
        return SimpleNamespace(one_or_none=lambda: (ws, "org"))

    db.execute.side_effect = execute
    catalog = catalog_adapter.ModuleSkillCatalog(lambda: db, lambda: modules)
    persistence = AsyncMock()
    persistence.list_visible.return_value = []
    persistence.get_by_id.return_value = None
    service = SkillService(persistence, module_catalog=catalog, user_skills_root=tmp_path / "user")
    service._ensure_workspace_access = AsyncMock()
    context = _context()

    rows = await service.list_visible_skills(context, "alpha")
    assert len(rows) == 1
    assert rows[0].catalog_ref == "example:weekly"
    assert rows[0].source == "module" and rows[0].prompt == ""
    assert [r.catalog_ref for r in await service.list_visible_skills(context, "beta")] == [
        "other:weekly"
    ]
    loaded = await service.get_skill(context, rows[0].id)
    assert loaded.prompt == "example private procedure"
    assert service.read_skill_package_file(loaded, "reference.md") == "example reference"
    assert service.read_skill_package_file(loaded, "../reference.md") is None
    assert await service.get_skill(context, module_skill_id("alpha", "other:weekly")) is None
    assert await service.get_skill(context, "bundled-slides") is None
    with pytest.raises(SkillPermissionError):
        await service.delete_skill(context, rows[0].id)
    with pytest.raises(SkillPermissionError):
        await service.write_requested_skill_package(context, rows[0].id, when_to_use="Requested")

    chat = ChatService(adapter=SimpleNamespace(), skills_service=service)
    assert (
        await chat.read_enabled_skill_body(context, "alpha", "weekly")
        == "example private procedure"
    )
    alpha.skills = []
    assert await service.list_visible_skills(context, "alpha") == []
    assert await service.get_skill(context, rows[0].id) is None
    assert await chat.read_enabled_skill_body(context, "alpha", "weekly") is None
    alpha.skills = ["example:weekly"]
    service._ensure_workspace_access.side_effect = SkillPermissionError("No membership")
    with pytest.raises(SkillPermissionError):
        await service.get_skill(context, rows[0].id)


@pytest.mark.asyncio
async def test_module_catalog_handles_same_slugs_and_unavailable_refs(tmp_path, monkeypatch):
    modules = {"example": _module(tmp_path, "example"), "other": _module(tmp_path, "other")}
    config = SimpleNamespace(slug="ws", skills=["example:weekly", "other:weekly", "missing:weekly"])
    monkeypatch.setattr(
        catalog_adapter,
        "live_settings",
        lambda: SimpleNamespace(organizations=[SimpleNamespace(slug="org", workspaces=[config])]),
    )
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(one_or_none=lambda: ("ws", "org"))
    persistence = AsyncMock()
    persistence.list_visible.return_value = []
    catalog = catalog_adapter.ModuleSkillCatalog(lambda: db, lambda: modules)
    service = SkillService(persistence, module_catalog=catalog)
    service._ensure_workspace_access = AsyncMock()
    rows = await service.list_visible_skills(_context(), "ws")
    assert {row.slug for row in rows} == {"example-weekly", "other-weekly"}
    chat = ChatService(adapter=SimpleNamespace(), skills_service=service)
    assert (
        await chat.read_enabled_skill_body(_context(), "ws", "other-weekly")
        == "other private procedure"
    )
    # Matching a workspace slug in a different organization must not grant access.
    db.execute.return_value = SimpleNamespace(one_or_none=lambda: ("ws", "different-org"))
    assert await service.list_visible_skills(_context(), "ws") == []
