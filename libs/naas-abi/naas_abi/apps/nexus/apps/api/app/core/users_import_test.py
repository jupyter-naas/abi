from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core.users_import import import_users, load_entries
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

NOW = datetime(2026, 1, 1)
TABLES = (UserModel, OrganizationModel, WorkspaceModel)


@pytest.fixture(autouse=True)
def iam(nexus_iam):
    """Roles are IAM's: ``u-existing`` already holds ``member`` of ``org-1``, changed
    after the snapshot was taken, and ``admin`` of nothing else."""
    nexus_iam.org("org-1")
    nexus_iam.workspace("org-1", "ws-1")
    nexus_iam.grant("u-existing", "member", "abi:nexus:organization/org-1")
    return nexus_iam


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
async def test_import_creates_missing_accounts_and_roles_and_never_overwrites(db, iam) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

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

    # Roles are IAM's. A role held stays (the snapshot says admin, it is member); a
    # person who held none gets what the snapshot names.
    assert await MEMBERSHIPS.role_at("u-existing", "abi:nexus:organization/org-1") == "member"
    assert await MEMBERSHIPS.role_at(new.id, "abi:nexus:organization/org-1") == "member"
    assert (
        await MEMBERSHIPS.role_at("u-existing", "abi:nexus:organization/org-1/nexus:workspace/ws-1")
        == "admin"
    )
    assert (
        await MEMBERSHIPS.role_at(new.id, "abi:nexus:organization/org-1/nexus:workspace/ws-1")
        == "viewer"
    )

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


@pytest.mark.asyncio
async def test_a_dry_run_gives_no_role(db) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

    report = await import_users(db, ENTRIES, apply=False)
    await db.rollback()

    assert report.workspace_memberships_created == 2
    assert (
        await MEMBERSHIPS.role_at("u-existing", "abi:nexus:organization/org-1/nexus:workspace/ws-1")
        is None
    )


@pytest.mark.asyncio
async def test_a_new_superadmin_is_a_platform_administrator_in_iam(db) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.iam import authz

    await import_users(db, [{"email": "root@example.com", "name": "Root", "is_superadmin": True}])
    await db.commit()
    root = (
        await db.execute(select(UserModel).where(UserModel.email == "root@example.com"))
    ).scalar_one()

    assert await authz.allowed("ManageSystem", user=root.id)


def test_load_entries_reads_the_snapshot_format(tmp_path) -> None:
    path = tmp_path / "config.users.yaml"
    path.write_text("# header\nusers:\n  - email: a@example.com\n    name: A\n")

    assert load_entries(path) == [{"email": "a@example.com", "name": "A"}]
