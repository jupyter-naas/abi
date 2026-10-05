"""Bundled skills are listed, and their bodies stay out of the chat catalog."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.chat.service import ChatService
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
from naas_abi.apps.nexus.apps.api.app.services.skills.port import (
    SkillRecord,
    SkillUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.skills.service import (
    SkillPermissionError,
    SkillService,
)
from naas_abi.skills.catalog import load_bundled_skills, read_package_file

# One sentence that lives only in each SKILL.md body.
_MARKERS = {
    "sheets": "The workbook JSON inside `workbook.html` is authoritative.",
    "slides": (
        "Hand the deck to SlidesAgent and write the open presentation HTML, "
        "not a PowerPoint file."
    ),
    "documents": (
        "Hand the memo to DocumentsAgent and fill the open document template "
        "instead of emitting a Word file."
    ),
    "web-research": (
        "Run search_public_web or web_search and cite only URLs the tool returned."
    ),
    "skill-creator": "Call create_skill to register the workspace skill.",
}

_EXPECTED = ("sheets", "slides", "documents", "web-research", "skill-creator")

_PACKAGE_FILES = {
    "sheets": (
        "SKILL.md",
        "references/research.md",
        "scripts/validate_workbook.py",
    ),
    "slides": ("SKILL.md", "references/presentation.md"),
    "documents": ("SKILL.md", "references/template.md"),
    "web-research": ("SKILL.md", "references/sources.md"),
    "skill-creator": ("SKILL.md", "references/package.md"),
}

_REFERENCE_MARKERS = {
    "slides": "1280x720",
    "documents": "fill_document_slots",
    "web-research": "search_public_web",
    "skill-creator": "when_to_use",
}


def _context() -> RequestContext:
    return RequestContext(
        token_data=TokenData(user_id="user-1", scopes={"*"}, is_authenticated=True)
    )


def _service(stored: list[SkillRecord] | None = None) -> tuple[SkillService, AsyncMock]:
    adapter = AsyncMock()
    adapter.list_visible = AsyncMock(return_value=list(stored or []))
    service = SkillService(adapter)
    service._ensure_workspace_access = AsyncMock()  # type: ignore[method-assign]
    return service, adapter


@pytest.mark.asyncio
async def test_bundled_skills_are_listed_without_inlining_bodies() -> None:
    loaded = load_bundled_skills()
    assert tuple(skill.slug for skill in loaded) == _EXPECTED
    for skill in loaded:
        assert skill.name.strip()
        assert skill.description.strip()
        assert skill.when_to_use.strip()
        marker = _MARKERS[skill.slug]
        assert marker in skill.body
        assert marker not in skill.description
        combined = "\n".join(
            (skill.name, skill.description, skill.when_to_use, skill.body)
        )
        assert "\u2014" not in combined
        assert "\u2013" not in combined

    service, adapter = _service()
    listed = await service.list_visible_skills(_context(), "ws-1")
    assert [row.slug for row in listed] == list(_EXPECTED)
    bodies = {skill.slug: skill.body for skill in loaded}
    for row in listed:
        assert row.builtin is True
        assert row.scope == "builtin"
        assert row.enabled is True
        assert row.id == f"bundled-{row.slug}"
        assert row.prompt == bodies[row.slug]
        assert row.when_to_use.strip()
        assert row.files == _PACKAGE_FILES[row.slug]
        if row.slug in _REFERENCE_MARKERS:
            note_path = _PACKAGE_FILES[row.slug][1]
            note = read_package_file(row.slug, note_path)
            assert note is not None
            assert _REFERENCE_MARKERS[row.slug] in note
            assert "\u2014" not in note
            assert "\u2013" not in note

    chat = ChatService(adapter=SimpleNamespace(), skills_service=service)
    context = _context()
    block = await chat._build_skills_block(context, "ws-1")
    assert "slug: sheets" in block
    assert "name: Sheets" in block
    assert "description: Spreadsheet work in Nexus Sheets." in block
    assert "when_to_use: The user wants a spreadsheet" in block
    for slug, marker in _MARKERS.items():
        assert marker not in block
        body = await chat.read_enabled_skill_body(context, "ws-1", slug)
        assert body is not None
        assert marker in body
    adapter.create.assert_not_called()


def test_skill_creator_registers_with_create_skill() -> None:
    """A create-a-skill request registers a workspace skill. It does not write a file."""
    skill = next(item for item in load_bundled_skills() if item.slug == "skill-creator")
    body = skill.body
    assert skill.when_to_use == (
        "The user asks to create a skill or register a workspace skill."
    )
    assert "Call create_skill" in body
    assert "write_file" not in body
    assert "skills/<slug>/SKILL.md" not in body
    note = read_package_file("skill-creator", "references/package.md")
    assert note is not None
    assert "Call `create_skill`" in note
    assert "write_file" not in note
    assert "skills/<slug>/SKILL.md" not in note
    assert "write_skill_package" in note


@pytest.mark.asyncio
async def test_saved_slug_hides_bundled_row_and_writes_are_rejected() -> None:
    saved = SkillRecord(
        id="user-sheets",
        workspace_id="ws-1",
        organization_id=None,
        user_id="user-1",
        name="My sheets",
        slug="sheets",
        description="mine",
        prompt="User sheets body, not the bundled one.",
        scope="user",
        enabled=True,
        last_used_at=None,
        created_at=datetime(2026, 2, 1),
        updated_at=datetime(2026, 2, 1),
    )
    service, adapter = _service([saved])
    listed = await service.list_visible_skills(_context(), "ws-1")
    sheets = [row for row in listed if row.slug == "sheets"]
    assert len(sheets) == 1
    assert sheets[0].prompt == saved.prompt
    assert sheets[0].files == ()
    assert "slides" in {row.slug for row in listed}

    with pytest.raises(SkillPermissionError):
        await service.update_skill(
            _context(), "bundled-slides", SkillUpdateInput(name="Nope")
        )
    with pytest.raises(SkillPermissionError):
        await service.delete_skill(_context(), "bundled-slides")
    adapter.update.assert_not_awaited()
    adapter.delete.assert_not_awaited()
