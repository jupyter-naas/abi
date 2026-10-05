"""User-invoked skill packages land on a path the catalog loader reads."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
from naas_abi.apps.nexus.apps.api.app.services.skills.port import SkillCreateInput, SkillRecord
from naas_abi.apps.nexus.apps.api.app.services.skills.service import SkillService
from naas_abi.skills.catalog import load_user_skills
from naas_abi.skills.writer import write_skill_package


def test_writer_emits_skill_md_the_loader_reads(tmp_path: Path) -> None:
    body = "Count the open items, then stop. No eval loop."
    path = write_skill_package(
        tmp_path,
        slug="open-items",
        name="Open items",
        description="Count what is still open.",
        when_to_use="The user asks what is still open.",
        body=body,
    )

    assert path == tmp_path / "open-items" / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    assert "name: Open items" in text
    assert "description: Count what is still open." in text
    assert "when_to_use: The user asks what is still open." in text
    assert body in text

    loaded = load_user_skills(tmp_path)
    assert [skill.slug for skill in loaded] == ["open-items"]
    assert loaded[0].name == "Open items"
    assert loaded[0].when_to_use == "The user asks what is still open."
    assert loaded[0].body == body
    assert "\u2014" not in text
    assert "\u2013" not in text


def test_writer_writes_extra_file_beside_skill_md(tmp_path: Path) -> None:
    path = write_skill_package(
        tmp_path,
        slug="open-items",
        name="Open items",
        description="Count what is still open.",
        when_to_use="The user asks what is still open.",
        body="Count the open items, then stop.",
        files=[{"path": "references/notes.md", "body": "A note beside the skill."}],
    )

    assert path == tmp_path / "open-items" / "SKILL.md"
    notes = tmp_path / "open-items" / "references" / "notes.md"
    assert notes.is_file()
    assert notes.read_text(encoding="utf-8") == "A note beside the skill."
    assert "name: Open items" in path.read_text(encoding="utf-8")


def test_writer_rejects_parent_directory_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="inside the package"):
        write_skill_package(
            tmp_path,
            slug="open-items",
            name="Open items",
            description="Count what is still open.",
            when_to_use="The user asks what is still open.",
            body="Count the open items.",
            files=[{"path": "../notes.md", "body": "nope"}],
        )
    assert list(tmp_path.rglob("*")) == []

    with pytest.raises(ValueError, match="inside the package"):
        write_skill_package(
            tmp_path,
            slug="open-items",
            name="Open items",
            description="Count what is still open.",
            when_to_use="The user asks what is still open.",
            body="Count the open items.",
            files=[{"path": "/tmp/notes.md", "body": "nope"}],
        )
    assert list(tmp_path.rglob("*")) == []


def test_writer_refuses_the_shipped_package_tree() -> None:
    shipped = Path(__file__).resolve().parent
    with pytest.raises(ValueError, match="shipped"):
        write_skill_package(
            shipped,
            slug="open-items",
            name="Open items",
            description="Count what is still open.",
            when_to_use="The user asks what is still open.",
            body="Do the count.",
        )
    assert not (shipped / "open-items").exists()


@pytest.mark.asyncio
async def test_prompt_create_does_not_write_a_package(tmp_path: Path) -> None:
    created = SkillRecord(
        id="row-1",
        workspace_id="ws-1",
        organization_id=None,
        user_id="user-1",
        name="Open items",
        slug="open-items",
        description="Count what is still open.",
        prompt="Count the open items.",
        scope="user",
        enabled=True,
        last_used_at=None,
        created_at=datetime(2026, 2, 1),
        updated_at=datetime(2026, 2, 1),
    )
    adapter = AsyncMock()
    adapter.create = AsyncMock(return_value=created)
    adapter.get_visible_by_slug = AsyncMock(return_value=None)
    adapter.list_visible = AsyncMock(
        side_effect=lambda workspace_id, _user_id: [created] if workspace_id == "ws-1" else []
    )
    service = SkillService(adapter, user_skills_root=tmp_path)
    service._ensure_workspace_access = AsyncMock()  # type: ignore[method-assign]
    context = RequestContext(
        token_data=TokenData(user_id="user-1", scopes={"*"}, is_authenticated=True)
    )
    await service.create_skill(
        context,
        SkillCreateInput(
            workspace_id="ws-1",
            user_id="user-1",
            name="Open items",
            slug="open-items",
            prompt="Count the open items.",
            description="Count what is still open.",
        ),
    )
    assert list(tmp_path.rglob("SKILL.md")) == []

    service.write_requested_skill_package(
        "ws-9",
        slug="open-items",
        name="Open items",
        description="Count what is still open.",
        when_to_use="The user asks what is still open.",
        body="Count the open items, then stop.",
    )
    listed = await service.list_visible_skills(context, "ws-9")
    package = next(row for row in listed if row.slug == "open-items")
    assert package.files == ("SKILL.md",)
    assert package.builtin is False
    assert "Count the open items, then stop." in package.prompt
    text = service.read_skill_package_file(package, "SKILL.md")
    assert text is not None
    assert "when_to_use: The user asks what is still open." in text

    hidden = await service.list_visible_skills(context, "ws-1")
    prompt_row = next(row for row in hidden if row.slug == "open-items")
    assert prompt_row.id == "row-1"
    assert prompt_row.files == ()
    assert service.read_skill_package_file(prompt_row, "SKILL.md") is None


@pytest.mark.asyncio
async def test_prompt_row_lists_extra_file_beside_skill_md(tmp_path: Path) -> None:
    created = SkillRecord(
        id="row-1",
        workspace_id="ws-1",
        organization_id=None,
        user_id="user-1",
        name="Open items",
        slug="open-items",
        description="Count what is still open.",
        prompt="Count the open items.",
        scope="user",
        enabled=True,
        last_used_at=None,
        created_at=datetime(2026, 2, 1),
        updated_at=datetime(2026, 2, 1),
    )
    adapter = AsyncMock()
    adapter.list_visible = AsyncMock(return_value=[created])
    adapter.get_by_id = AsyncMock(return_value=created)
    service = SkillService(adapter, user_skills_root=tmp_path)
    service._ensure_workspace_access = AsyncMock()  # type: ignore[method-assign]
    context = RequestContext(
        token_data=TokenData(user_id="user-1", scopes={"*"}, is_authenticated=True)
    )
    service.write_requested_skill_package(
        "ws-1",
        slug="open-items",
        name="Open items",
        description="Count what is still open.",
        when_to_use="The user asks what is still open.",
        body="Count the open items, then stop.",
        files=[{"path": "references/notes.md", "body": "A note beside the skill."}],
    )

    listed = await service.list_visible_skills(context, "ws-1")
    row = next(item for item in listed if item.id == "row-1")
    assert "SKILL.md" in row.files
    assert "references/notes.md" in row.files
    assert service.read_skill_package_file(row, "references/notes.md") == "A note beside the skill."
    assert not any(item.id.startswith("pkg.") and item.slug == "open-items" for item in listed)

    loaded = await service.get_skill(context, "row-1")
    assert loaded is not None
    assert "references/notes.md" in loaded.files
