from __future__ import annotations

import contextlib
import os
from datetime import UTC, datetime
from pathlib import Path
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
        record = _skill(
            "skill-new",
            data.slug,
            name=data.name,
            description=data.description or "",
            prompt=data.prompt,
            scope=data.scope,
        )
        self.skills.append(record)
        return record

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


def test_read_workspace_skill_returns_the_full_prompt_unclipped(skills) -> None:
    marker = "UNIQUE_SKILL_BODY_SENTENCE_PAST_THE_CLIP"
    prompt = ("instruction " * 400) + marker
    assert len(prompt) > 4000
    skills["service"].skills.append(
        _skill(
            "skill-long",
            "long-form",
            name="Long form",
            description="A long procedure",
            prompt=prompt,
        )
    )
    tool = tools_module.make_read_workspace_skill_tool()
    result = tool.invoke({"slug": "/long-form"})
    assert result == prompt
    assert marker in result


def test_read_workspace_skill_does_not_return_office_procedure_bodies(skills) -> None:
    """Sheets, slides, and documents stay catalog rows. The chat tool must not
    hand their procedure to whichever agent is running."""
    sheets_body = "The workbook JSON inside `workbook.html` is authoritative."
    slides_body = (
        "Hand the deck to SlidesAgent and write the open presentation HTML, "
        "not a PowerPoint file."
    )
    documents_body = (
        "Hand the memo to DocumentsAgent and fill the open document template "
        "instead of emitting a Word file."
    )
    research_body = (
        "Run search_public_web or web_search and cite only URLs the tool returned."
    )
    skills["service"].skills.extend(
        [
            _skill("skill-sheets", "sheets", prompt=sheets_body),
            _skill("skill-slides", "slides", prompt=slides_body),
            _skill("skill-documents", "documents", prompt=documents_body),
            _skill("skill-research", "web-research", prompt=research_body),
        ]
    )
    tool = tools_module.make_read_workspace_skill_tool()

    for slug, body in (
        ("sheets", sheets_body),
        ("/slides", slides_body),
        ("documents", documents_body),
    ):
        result = tool.invoke({"slug": slug})
        assert body not in result
        assert "office" in result.lower()

    research = tool.invoke({"slug": "web-research"})
    assert research == research_body


def test_read_workspace_skill_skips_disabled_unknown_and_reserved(skills) -> None:
    secret = "DISABLED_BODY_MUST_STAY_HIDDEN"
    skills["service"].skills.append(
        _skill("skill-off", "disabled-one", prompt=secret, enabled=False)
    )
    tool = tools_module.make_read_workspace_skill_tool()
    disabled = tool.invoke({"slug": "disabled-one"})
    unknown = tool.invoke({"slug": "missing-skill"})
    reserved = tool.invoke({"slug": "/create-skill"})
    assert secret not in disabled
    assert "No enabled skill" in disabled
    assert "No enabled skill" in unknown
    assert "reserved" in reserved
    assert secret not in reserved


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


def _home_skills_root() -> Path:
    return Path(os.path.expanduser("~")) / "skills"


def _under_home_skills(path: Path) -> bool:
    root = _home_skills_root()
    try:
        candidate = path.expanduser().resolve()
        base = root.resolve()
    except OSError:
        candidate = path.expanduser()
        base = root
    if candidate == base:
        return True
    try:
        candidate.relative_to(base)
    except ValueError:
        return False
    return True


def _watch_home_skills_writes(monkeypatch) -> list[Path]:
    """Record writes under ~/skills. The tool must not land there."""
    hits: list[Path] = []

    def consider(path: object) -> None:
        try:
            candidate = Path(os.fspath(path))  # type: ignore[arg-type]
        except TypeError:
            return
        if _under_home_skills(candidate):
            hits.append(candidate)

    real_write_text = Path.write_text
    real_write_bytes = Path.write_bytes
    real_mkdir = Path.mkdir
    real_open = open

    def write_text(self, *args, **kwargs):
        consider(self)
        return real_write_text(self, *args, **kwargs)

    def write_bytes(self, *args, **kwargs):
        consider(self)
        return real_write_bytes(self, *args, **kwargs)

    def mkdir(self, *args, **kwargs):
        consider(self)
        return real_mkdir(self, *args, **kwargs)

    def tracked_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            consider(file)
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write_text)
    monkeypatch.setattr(Path, "write_bytes", write_bytes)
    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr("builtins.open", tracked_open)
    return hits


def test_create_skill_records_a_listed_skill_and_skips_home_skills(
    skills, monkeypatch
) -> None:
    """create_skill stores name, description, and prompt. It does not write ~/skills."""
    import asyncio

    hits = _watch_home_skills_writes(monkeypatch)
    name = "Weekly Sales Summary"
    description = "Weekly sales table for the workspace."
    prompt = "Summarize last week's sales as a Markdown table."
    skills["tools"]["create_skill"].invoke(
        {"name": name, "description": description, "prompt": prompt}
    )

    created = skills["service"].created[-1]
    assert created.name == name
    assert created.description == description
    assert created.prompt == prompt

    listed = asyncio.run(skills["service"].list_visible_skills(object(), "ws-1"))
    match = next(row for row in listed if row.name == name)
    assert match.name == name
    assert match.description == description
    assert match.prompt == prompt
    assert hits == []


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


def test_module_skill_read_fetches_body_after_catalog_match(skills):
    from dataclasses import replace
    from unittest.mock import AsyncMock

    service = skills["service"]
    row = _skill(
        "module-row", "weekly-report", prompt="", source="module", builtin=True
    )
    service.skills = [row]
    service.get_skill = AsyncMock(return_value=replace(row, prompt="Module procedure"))
    result = tools_module.make_read_workspace_skill_tool().invoke(
        {"slug": "weekly-report"}
    )
    assert result == "Module procedure"
    service.get_skill.assert_awaited_once()
