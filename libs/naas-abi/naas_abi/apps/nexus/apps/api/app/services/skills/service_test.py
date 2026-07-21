from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.skills.adapters.secondary.postgres import (
    SkillSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.skills.port import (
    SkillCreateInput,
    SkillRecord,
    SkillUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.skills.service import (
    SkillPermissionError,
    SkillService,
    SkillValidationError,
    normalize_slug,
)


def _record(**overrides) -> SkillRecord:
    defaults: dict = {
        "id": "skill-1",
        "workspace_id": "ws-1",
        "organization_id": None,
        "user_id": "user-1",
        "name": "Summarize",
        "slug": "summarize",
        "description": "",
        "prompt": "Summarize the following",
        "scope": "user",
        "enabled": True,
        "last_used_at": None,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    defaults.update(overrides)
    return SkillRecord(**defaults)


def _context(user_id: str = "user-1"):
    from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData

    return RequestContext(
        token_data=TokenData(user_id=user_id, scopes={"*"}, is_authenticated=True)
    )


def _service(adapter) -> SkillService:
    service = SkillService(adapter)
    service._ensure_workspace_access = AsyncMock()  # type: ignore[method-assign]
    return service


def test_normalize_slug() -> None:
    assert normalize_slug("My Cool Skill!") == "my-cool-skill"
    assert normalize_slug("  weekly_report  ") == "weekly-report"
    assert normalize_slug("/slash") == "slash"


@pytest.mark.asyncio
async def test_create_skill_normalizes_slug_and_creates() -> None:
    adapter = AsyncMock()
    adapter.get_visible_by_slug = AsyncMock(return_value=None)
    adapter.create = AsyncMock(side_effect=lambda data: _record(slug=data.slug))
    service = _service(adapter)

    created = await service.create_skill(
        _context(),
        SkillCreateInput(
            workspace_id="ws-1",
            user_id="user-1",
            name="Weekly Report",
            slug="Weekly Report",
            prompt="Write the weekly report",
        ),
    )

    assert created.slug == "weekly-report"
    adapter.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_skill_rejects_reserved_and_duplicate_slug() -> None:
    adapter = AsyncMock()
    adapter.get_visible_by_slug = AsyncMock(return_value=None)
    service = _service(adapter)

    with pytest.raises(SkillValidationError):
        await service.create_skill(
            _context(),
            SkillCreateInput(
                workspace_id="ws-1",
                user_id="user-1",
                name="Skills",
                slug="skills",
                prompt="x",
            ),
        )

    adapter.get_visible_by_slug = AsyncMock(return_value=_record(id="other"))
    with pytest.raises(SkillValidationError):
        await service.create_skill(
            _context(),
            SkillCreateInput(
                workspace_id="ws-1",
                user_id="user-1",
                name="Summarize",
                slug="summarize",
                prompt="x",
            ),
        )


@pytest.mark.asyncio
async def test_create_skill_rejects_invalid_scope() -> None:
    adapter = AsyncMock()
    service = _service(adapter)

    with pytest.raises(SkillValidationError):
        await service.create_skill(
            _context(),
            SkillCreateInput(
                workspace_id="ws-1",
                user_id="user-1",
                name="S",
                slug="s",
                prompt="x",
                scope="global",
            ),
        )


@pytest.mark.asyncio
async def test_update_user_scoped_skill_rejected_for_non_creator() -> None:
    adapter = AsyncMock()
    adapter.get_by_id = AsyncMock(return_value=_record(user_id="creator"))
    service = _service(adapter)

    with pytest.raises(SkillPermissionError):
        await service.update_skill(
            _context(user_id="someone-else"),
            "skill-1",
            SkillUpdateInput(name="New"),
        )


@pytest.mark.asyncio
async def test_update_workspace_scoped_skill_allowed_for_member() -> None:
    adapter = AsyncMock()
    adapter.get_by_id = AsyncMock(return_value=_record(scope="workspace", user_id="creator"))
    adapter.update = AsyncMock(return_value=_record(scope="workspace", name="New"))
    service = _service(adapter)

    updated = await service.update_skill(
        _context(user_id="someone-else"),
        "skill-1",
        SkillUpdateInput(name="New"),
    )

    assert updated is not None
    assert updated.name == "New"


@pytest.mark.asyncio
async def test_delete_user_scoped_skill_rejected_for_non_creator() -> None:
    adapter = AsyncMock()
    adapter.get_by_id = AsyncMock(return_value=_record(user_id="creator"))
    service = _service(adapter)

    with pytest.raises(SkillPermissionError):
        await service.delete_skill(_context(user_id="someone-else"), "skill-1")


@pytest.mark.asyncio
async def test_adapter_maps_row_to_record() -> None:
    row = SimpleNamespace(
        id="skill-1",
        workspace_id="ws-1",
        organization_id="org-1",
        user_id="user-1",
        name="Summarize",
        slug="summarize",
        description="Sums things up",
        prompt="Summarize the following",
        scope="organization",
        enabled=True,
        last_used_at=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db = AsyncMock()
    scalars = SimpleNamespace(all=lambda: [row], first=lambda: row)
    db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: row, scalars=lambda: scalars)
    )

    adapter = SkillSecondaryAdapterPostgres(db=db)
    skills = await adapter.list_visible("ws-1", "user-1")

    assert len(skills) == 1
    assert skills[0].slug == "summarize"
    assert skills[0].scope == "organization"
    assert skills[0].organization_id == "org-1"
