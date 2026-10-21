from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core.users_import import import_users, load_entries
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


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        for model in TABLES:
            await conn.run_sync(lambda sync, m=model: m.__table__.create(sync))
    async with AsyncSession(engine) as session:
        session.add(
            UserModel(
                id="u-existing",
                email="existing@example.com",
                name="Renamed In UI",
                hashed_password="x",
                is_superadmin=False,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.add(
            OrganizationModel(
                id="org-1",
                name="Org",
                slug="org",
                owner_id="u-existing",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.add(
            WorkspaceModel(
                id="ws-1",
                name="One",
                slug="one",
                owner_id="u-existing",
                organization_id="org-1",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        # Role changed in the UI after the snapshot was taken.
        session.add(
            OrganizationMemberModel(
                id="om-1",
                organization_id="org-1",
                user_id="u-existing",
                role="member",
                created_at=NOW,
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


ENTRIES = [
    {
        "email": "Existing@Example.com",
        "name": "Snapshot Name",
        "is_superadmin": True,
        "organizations": [{"slug": "org", "role": "admin"}],
        "workspaces": [{"slug": "one", "role": "admin"}],
    },
    {
        "email": "new@example.com",
        "name": None,
        "organizations": [
            {"slug": "org", "role": "member"},
            {"slug": "missing-org", "role": "member"},
        ],
        "workspaces": [{"slug": "one", "role": "viewer"}, {"slug": "missing-ws", "role": "member"}],
    },
]


@pytest.mark.asyncio
async def test_import_creates_missing_rows_and_never_overwrites(db) -> None:
    report = await import_users(db, ENTRIES)
    await db.commit()

    existing = (
        await db.execute(select(UserModel).where(UserModel.id == "u-existing"))
    ).scalar_one()
    assert existing.name == "Renamed In UI"
    assert existing.is_superadmin is False

    new = (
        await db.execute(select(UserModel).where(UserModel.email == "new@example.com"))
    ).scalar_one()
    assert new.name == "new"

    org_roles = {
        row.user_id: row.role
        for row in (await db.execute(select(OrganizationMemberModel))).scalars()
    }
    assert org_roles == {"u-existing": "member", new.id: "member"}

    ws_roles = {
        row.user_id: row.role for row in (await db.execute(select(WorkspaceMemberModel))).scalars()
    }
    assert ws_roles == {"u-existing": "admin", new.id: "viewer"}

    assert report.users_created == 1
    assert report.organization_memberships_created == 1
    assert report.workspace_memberships_created == 2
    assert sorted(report.missing) == ["organization missing-org", "workspace missing-ws"]


@pytest.mark.asyncio
async def test_import_is_idempotent(db) -> None:
    await import_users(db, ENTRIES)
    await db.commit()
    again = await import_users(db, ENTRIES)

    assert again.users_created == 0
    assert again.organization_memberships_created == 0
    assert again.workspace_memberships_created == 0


def test_load_entries_reads_the_snapshot_format(tmp_path) -> None:
    path = tmp_path / "config.users.yaml"
    path.write_text("# header\nusers:\n  - email: a@example.com\n    name: A\n")

    assert load_entries(path) == [{"email": "a@example.com", "name": "A"}]
