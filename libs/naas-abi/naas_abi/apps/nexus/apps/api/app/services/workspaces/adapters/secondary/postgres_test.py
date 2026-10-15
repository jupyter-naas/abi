from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
    WorkspaceSecondaryAdapterPostgres,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

NOW = datetime(2026, 1, 1)
TABLES = (
    UserModel,
    OrganizationModel,
    OrganizationMemberModel,
    WorkspaceModel,
    WorkspaceMemberModel,
)


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
                    hashed_password="x",
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
        session.add_all(
            [
                OrganizationMemberModel(
                    id="om-1",
                    organization_id="org-1",
                    user_id="org-admin",
                    role="admin",
                    created_at=NOW,
                ),
                OrganizationMemberModel(
                    id="om-2",
                    organization_id="org-1",
                    user_id="org-member",
                    role="member",
                    created_at=NOW,
                ),
            ]
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
        session.add(
            WorkspaceMemberModel(
                id="wm-1", workspace_id="ws-1", user_id="ws-member", role="owner", created_at=NOW
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_members_include_org_owners_and_admins_as_inherited(db) -> None:
    adapter = WorkspaceSecondaryAdapterPostgres(db=db)

    members = await adapter.list_workspace_members("ws-1")

    assert [(m.user_id, m.role, m.source) for m in members] == [
        ("ws-member", "owner", "workspace"),
        ("founder", "owner", "organization"),
        ("org-admin", "admin", "organization"),
    ]


@pytest.mark.asyncio
async def test_org_admin_lists_every_org_workspace(db) -> None:
    adapter = WorkspaceSecondaryAdapterPostgres(db=db)

    assert [w.id for w in await adapter.list_workspaces_for_user("org-admin")] == ["ws-1"]
    assert await adapter.list_workspaces_for_user("org-member") == []
    assert await adapter.get_workspace_role("org-admin", "ws-1") == "admin"


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
