from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi_core.services.agent.context import agent_user_id, agent_workspace_id

from naas_abi.agents.feature.context import nexus_feature_context
from naas_abi.apps.nexus.apps.api.app.services.skills.port import SkillRecord
from naas_abi.tools import skills_tools as tools_module

NOW = datetime(2026, 9, 17, tzinfo=UTC)


def _skill(skill_id: str, slug: str, **extra: Any) -> SkillRecord:
    return SkillRecord(
        id=skill_id,
        workspace_id="ws-1",
        organization_id=None,
        user_id=extra.pop("user_id", "user-1"),
        name=extra.pop("name", slug.replace("-", " ").title()),
        slug=slug,
        description=extra.pop("description", f"{slug} description"),
        prompt=extra.pop("prompt", f"Run {slug}."),
        scope=extra.pop("scope", "user"),
        enabled=extra.pop("enabled", True),
        last_used_at=None,
        created_at=NOW,
        updated_at=NOW,
        **extra,
    )


class _FakeSkillsService:
    def __init__(self, skills: list[SkillRecord]) -> None:
        self.skills = skills
        self.created: list[Any] = []
        self.updated: list[tuple[str, Any]] = []
        self.deleted: list[str] = []

    async def list_visible_skills(self, context, workspace_id):
        del context, workspace_id
        return list(self.skills)

    async def create_skill(self, context, data):
        del context
        self.created.append(data)
        return _skill(
            "skill-new",
            data.slug,
            name=data.name,
            description=data.description or "",
            prompt=data.prompt,
            scope=data.scope,
        )

    async def update_skill(self, context, skill_id, updates):
        del context
        self.updated.append((skill_id, updates))
        found = next(s for s in self.skills if s.id == skill_id)
        return _skill(
            skill_id,
            updates.slug or found.slug,
            name=updates.name or found.name,
            scope=updates.scope or found.scope,
            enabled=found.enabled if updates.enabled is None else updates.enabled,
        )

    async def delete_skill(self, context, skill_id):
        del context
        self.deleted.append(skill_id)
        return True


@pytest.fixture
def skills(monkeypatch) -> dict[str, Any]:
    service = _FakeSkillsService(
        [_skill("skill-1", "weekly-report"), _skill("skill-2", "standup-notes")]
    )

    def _run_db(fn):
        import asyncio

        return asyncio.run(fn(object()))

    async def _require_member(db, user_id, workspace_id):
        del db, user_id, workspace_id
        return "owner"

    monkeypatch.setattr(tools_module, "run_db", _run_db)
    monkeypatch.setattr(tools_module, "require_member", _require_member)
    monkeypatch.setattr(tools_module, "request_context", lambda user_id: user_id)
    monkeypatch.setattr(
        tools_module, "bound_session", lambda db: contextlib.nullcontext()
    )
    monkeypatch.setattr(
        tools_module, "_registry", lambda: SimpleNamespace(skills=service)
    )

    tokens = [
        agent_user_id.set("user-1"),
        agent_workspace_id.set("ws-1"),
        nexus_feature_context.set(None),
    ]
    yield {
        "service": service,
        "tools": {t.name: t for t in tools_module.skills_tools()},
    }
    agent_user_id.reset(tokens[0])
    agent_workspace_id.reset(tokens[1])
    nexus_feature_context.reset(tokens[2])


def _open(skill_id: str) -> None:
    nexus_feature_context.set(
        {"key": "skills", "resource": {"kind": "skill", "id": skill_id}}
    )


def test_list_returns_the_commands_and_scopes(skills) -> None:
    out = skills["tools"]["list_workspace_skills"].invoke({})
    slugs = [row["slug"] for row in out["skills"]]

    assert out["total"] == 2
    assert slugs == ["weekly-report", "standup-notes"]
    assert out["skills"][0]["scope"] == "user"


def test_list_filters_on_a_query(skills) -> None:
    out = skills["tools"]["list_workspace_skills"].invoke({"query": "standup"})
    assert [row["slug"] for row in out["skills"]] == ["standup-notes"]


def test_get_defaults_to_the_open_skill_and_carries_the_prompt(skills) -> None:
    _open("skill-2")
    out = skills["tools"]["get_workspace_skill"].invoke({})

    assert out["slug"] == "standup-notes"
    assert out["prompt"] == "Run standup-notes."


def test_get_accepts_a_slash_command(skills) -> None:
    out = skills["tools"]["get_workspace_skill"].invoke({"skill": "/weekly-report"})
    assert out["id"] == "skill-1"


def test_get_without_an_open_skill_asks_for_one(skills) -> None:
    out = skills["tools"]["get_workspace_skill"].invoke({})
    assert "No skill is open" in out["error"]


def test_create_saves_the_skill_and_reports_its_command(skills) -> None:
    out = skills["tools"]["create_skill"].invoke(
        {
            "name": "Weekly Sales Summary",
            "prompt": "Summarize last week's sales as a Markdown table.",
            "scope": "workspace",
        }
    )
    created = skills["service"].created[0]

    assert out["saved"] is True
    assert out["command"] == "/weekly-sales-summary"
    assert created.slug == "weekly-sales-summary"  # slugified from the name
    assert created.workspace_id == "ws-1"
    assert created.user_id == "user-1"
    assert created.scope == "workspace"


def test_create_refuses_a_skill_with_no_prompt(skills) -> None:
    out = skills["tools"]["create_skill"].invoke({"name": "Empty", "prompt": "  "})
    assert "prompt is required" in out["error"]
    assert skills["service"].created == []


def test_update_only_sends_the_fields_that_were_passed(skills) -> None:
    _open("skill-1")
    out = skills["tools"]["update_skill"].invoke({"enabled": False})
    skill_id, updates = skills["service"].updated[0]

    assert skill_id == "skill-1"
    assert updates.enabled is False
    assert updates.name is None and updates.prompt is None
    assert out["updated"] == ["enabled"]
    assert out["enabled"] is False


def test_update_without_a_change_says_so(skills) -> None:
    _open("skill-1")
    out = skills["tools"]["update_skill"].invoke({})

    assert "Nothing to change" in out["error"]
    assert skills["service"].updated == []


def test_update_rejects_an_unknown_skill(skills) -> None:
    out = skills["tools"]["update_skill"].invoke({"skill": "nope", "name": "X"})

    assert "No visible skill nope" in out["error"]
    assert skills["service"].updated == []


def test_delete_removes_the_named_skill(skills) -> None:
    out = skills["tools"]["delete_skill"].invoke({"skill": "standup-notes"})

    assert skills["service"].deleted == ["skill-2"]
    assert out == {"deleted": True, "slug": "standup-notes", "name": "Standup Notes"}


def test_write_tools_are_the_ones_the_web_refreshes_on() -> None:
    """stores/skills.ts mirrors this list to refetch the catalog."""
    from pathlib import Path

    from naas_abi.tools.nexus_source_tools import PACKAGE_ROOT

    names = {t.name for t in tools_module.skills_tools()}
    assert set(tools_module.SKILL_WRITE_TOOLS) <= names

    web = Path(PACKAGE_ROOT) / "apps/nexus/apps/web/src/stores/skills.ts"
    if not web.is_file():
        pytest.skip("web sources not shipped")
    block = web.read_text(encoding="utf-8").split("SKILL_WRITE_TOOLS = [", 1)[1]
    listed = set(block.split("]", 1)[0].replace("'", "").replace(" ", "").split(","))
    assert listed - {""} == set(tools_module.SKILL_WRITE_TOOLS)
