from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core.workspace_access import (
    accessible_workspace_ids,
    max_role,
    resolve_workspace_role,
)
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

NOW = datetime(2026, 1, 1)
TABLES = (
    UserModel,
    OrganizationModel,
    OrganizationMemberModel,
    WorkspaceModel,
    WorkspaceMemberModel,
)


def _user(user_id: str) -> UserModel:
    return UserModel(
        id=user_id,
        email=f"{user_id}@example.com",
        name=user_id,
        hashed_password="x",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        for model in TABLES:
            await conn.run_sync(lambda sync, m=model: m.__table__.create(sync))
    async with AsyncSession(engine) as session:
        session.add_all(
            [
                _user(uid)
                for uid in (
                    "founder",
                    "org-owner",
                    "org-admin",
                    "org-member",
                    "ws-admin",
                    "stranger",
                )
            ]
        )
        session.add_all(
            [
                OrganizationModel(
                    id="org-1",
                    name="Org",
                    slug="org",
                    owner_id="founder",
                    created_at=NOW,
                    updated_at=NOW,
                ),
                OrganizationModel(
                    id="org-2",
                    name="Other",
                    slug="other",
                    owner_id="stranger",
                    created_at=NOW,
                    updated_at=NOW,
                ),
            ]
        )
        session.add_all(
            [
                OrganizationMemberModel(
                    id="om-1",
                    organization_id="org-1",
                    user_id="org-owner",
                    role="owner",
                    created_at=NOW,
                ),
                OrganizationMemberModel(
                    id="om-2",
                    organization_id="org-1",
                    user_id="org-admin",
                    role="admin",
                    created_at=NOW,
                ),
                OrganizationMemberModel(
                    id="om-3",
                    organization_id="org-1",
                    user_id="org-member",
                    role="member",
                    created_at=NOW,
                ),
            ]
        )
        session.add_all(
            [
                WorkspaceModel(
                    id="ws-1",
                    name="One",
                    slug="one",
                    owner_id="founder",
                    organization_id="org-1",
                    created_at=NOW,
                    updated_at=NOW,
                ),
                WorkspaceModel(
                    id="ws-2",
                    name="Two",
                    slug="two",
                    owner_id="org-admin",
                    organization_id="org-1",
                    created_at=NOW,
                    updated_at=NOW,
                ),
                WorkspaceModel(
                    id="ws-other",
                    name="Other",
                    slug="ws-other",
                    owner_id="stranger",
                    organization_id="org-2",
                    created_at=NOW,
                    updated_at=NOW,
                ),
                WorkspaceModel(
                    id="ws-solo",
                    name="Solo",
                    slug="solo",
                    owner_id="stranger",
                    organization_id=None,
                    created_at=NOW,
                    updated_at=NOW,
                ),
            ]
        )
        session.add_all(
            [
                WorkspaceMemberModel(
                    id="wm-1", workspace_id="ws-1", user_id="ws-admin", role="admin", created_at=NOW
                ),
                WorkspaceMemberModel(
                    id="wm-2",
                    workspace_id="ws-1",
                    user_id="org-member",
                    role="viewer",
                    created_at=NOW,
                ),
            ]
        )
        await session.commit()
        yield session
    await engine.dispose()


def test_max_role_ranks_and_ignores_missing() -> None:
    assert max_role(None, "viewer", "admin", None) == "admin"
    assert max_role("owner", "member") == "owner"
    assert max_role(None, None) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user_id", "workspace_id", "expected"),
    [
        ("founder", "ws-1", "owner"),  # workspace owner_id
        ("founder", "ws-2", "owner"),  # organization owner_id inherits owner
        ("org-owner", "ws-1", "owner"),  # org role owner inherits owner
        ("org-admin", "ws-1", "admin"),  # org role admin inherits admin
        ("org-admin", "ws-2", "owner"),  # explicit workspace owner beats inherited admin
        ("org-member", "ws-1", "viewer"),  # org member gets only the explicit row
        ("org-member", "ws-2", None),
        ("ws-admin", "ws-1", "admin"),
        ("org-owner", "ws-other", None),  # no inheritance across orgs
        ("org-owner", "ws-solo", None),
        ("stranger", "ws-1", None),
        ("founder", "missing", None),
    ],
)
async def test_resolve_workspace_role(db, user_id: str, workspace_id: str, expected) -> None:
    assert await resolve_workspace_role(db, user_id, workspace_id) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user_id", "expected"),
    [
        ("founder", {"ws-1", "ws-2"}),
        ("org-owner", {"ws-1", "ws-2"}),
        ("org-admin", {"ws-1", "ws-2"}),
        ("org-member", {"ws-1"}),
        ("ws-admin", {"ws-1"}),
        ("stranger", {"ws-other", "ws-solo"}),
    ],
)
async def test_accessible_workspace_ids(db, user_id: str, expected: set[str]) -> None:
    rows = await db.execute(
        select(WorkspaceModel.id).where(WorkspaceModel.id.in_(accessible_workspace_ids(user_id)))
    )
    assert {row[0] for row in rows} == expected


@pytest.mark.asyncio
async def test_accessible_workspace_ids_can_require_a_minimum_role(db) -> None:
    rows = await db.execute(
        select(WorkspaceModel.id).where(
            WorkspaceModel.id.in_(accessible_workspace_ids("ws-admin", min_role="admin"))
        )
    )
    assert {row[0] for row in rows} == {"ws-1"}
    rows = await db.execute(
        select(WorkspaceModel.id).where(
            WorkspaceModel.id.in_(accessible_workspace_ids("org-member", min_role="admin"))
        )
    )
    assert {row[0] for row in rows} == set()
