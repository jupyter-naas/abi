from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
    WorkspaceSecondaryAdapterPostgres,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

NOW = datetime(2026, 1, 1)
TABLES = (UserModel, OrganizationModel, WorkspaceModel)


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        for model in TABLES:
            await conn.run_sync(lambda sync, m=model: m.__table__.create(sync))
    async with AsyncSession(engine) as session:
        for uid in ("founder", "org-admin", "org-member", "ws-member"):
            session.add(
                UserModel(
                    id=uid,
                    email=f"{uid}@example.com",
                    name=uid,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        session.add(
            OrganizationModel(
                id="org-1",
                name="Org",
                slug="org",
                owner_id="founder",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.add(
            WorkspaceModel(
                id="ws-1",
                name="One",
                slug="one",
                owner_id="ws-member",
                organization_id="org-1",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_description_is_saved_and_can_be_cleared(db) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceUpdateInput

    adapter = WorkspaceSecondaryAdapterPostgres(db=db)

    updated = await adapter.update_workspace(
        workspace_id="ws-1",
        updates=WorkspaceUpdateInput(name="Audit FR", description="Audit engagements in France"),
    )
    assert (updated.name, updated.description) == ("Audit FR", "Audit engagements in France")

    cleared = await adapter.update_workspace(
        workspace_id="ws-1", updates=WorkspaceUpdateInput(description="")
    )
    assert (cleared.name, cleared.description) == ("Audit FR", "")


@pytest.mark.asyncio
async def test_group_is_saved_and_a_blank_group_clears_it(db) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceUpdateInput

    adapter = WorkspaceSecondaryAdapterPostgres(db=db)

    grouped = await adapter.update_workspace(
        workspace_id="ws-1", updates=WorkspaceUpdateInput(workspace_group=" Key Accounts ")
    )
    assert grouped.workspace_group == "Key Accounts"

    cleared = await adapter.update_workspace(
        workspace_id="ws-1", updates=WorkspaceUpdateInput(workspace_group="  ")
    )
    assert cleared.workspace_group is None


@pytest.mark.asyncio
async def test_create_saves_the_description_and_a_trimmed_group(db) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceCreateInput

    adapter = WorkspaceSecondaryAdapterPostgres(db=db)

    created = await adapter.create_workspace(
        WorkspaceCreateInput(
            name="Two",
            slug="two",
            owner_id="founder",
            organization_id="org-1",
            description="Second workspace",
            workspace_group=" Key Accounts ",
        )
    )
    assert (created.slug, created.description, created.workspace_group) == (
        "two",
        "Second workspace",
        "Key Accounts",
    )

    ungrouped = await adapter.create_workspace(
        WorkspaceCreateInput(name="Three", slug="three", owner_id="founder", workspace_group="  ")
    )
    assert ungrouped.workspace_group is None


@pytest.mark.asyncio
async def test_a_workspace_abandoned_after_a_failed_flush_leaves_nothing(db) -> None:
    """A create that fails at the flush that follows it: the session refuses
    everything until rolled back, so the row goes with the rollback and the IAM
    scope is dropped directly, never through a delete it would refuse."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceCreateInput
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import WorkspaceService
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    adapter = WorkspaceSecondaryAdapterPostgres(db=db)
    memberships = SimpleNamespace(drop_scope=AsyncMock())
    service = WorkspaceService(adapter=adapter, memberships=memberships)
    created = await adapter.create_workspace(
        WorkspaceCreateInput(name="Two", slug="two", owner_id="founder", organization_id="org-1")
    )
    db.add(WorkspaceModel(id=created.id, name="Dup", slug="dup", created_at=NOW, updated_at=NOW))
    with pytest.raises(IntegrityError):
        await db.flush()

    await service.abandon_workspace(created)

    memberships.drop_scope.assert_awaited_once_with("org-1", created.id)
    ids = (await db.execute(select(WorkspaceModel.id))).scalars().all()
    assert ids == ["ws-1"]
