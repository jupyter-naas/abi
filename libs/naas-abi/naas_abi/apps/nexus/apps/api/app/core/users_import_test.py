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
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
        CONTAINER_DEFAULTS,
    )

    # The records another test's IAM made are not this one's.
    CONTAINER_DEFAULTS._known.clear()
    CONTAINER_DEFAULTS._missing.clear()
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


@pytest.mark.asyncio
async def test_new_people_are_invited_and_name_their_provider(db) -> None:
    """As the configuration's (core/org_seed.py): their verified sign-in at that
    provider opens the row; an existing row no provider signs in yet is only given
    its provider."""
    providers = ({"builtin": "builtin", "corp": "zitadel"}, "corp")

    report = await import_users(
        db,
        [
            {"email": "new@example.com", "name": "New"},
            {"email": "kc@example.com", "name": "Kc", "provider": "builtin"},
            {"email": "existing@example.com", "name": "Snapshot"},
        ],
        providers=providers,
    )
    await db.commit()

    rows = {u.email: u for u in (await db.execute(select(UserModel))).scalars()}
    assert (rows["new@example.com"].status, rows["new@example.com"].idp_provider) == (
        "invited",
        "corp",
    )
    assert rows["kc@example.com"].idp_provider == "builtin"
    assert (rows["existing@example.com"].status, rows["existing@example.com"].idp_provider) == (
        "active",
        "corp",
    )
    assert report.created_emails == ["new@example.com", "kc@example.com"]


def test_load_entries_reads_the_snapshot_format(tmp_path) -> None:
    path = tmp_path / "config.users.yaml"
    path.write_text("# header\nusers:\n  - email: a@example.com\n    name: A\n")

    assert load_entries(path) == [{"email": "a@example.com", "name": "A"}]


@pytest.mark.asyncio
async def test_the_access_model_format_is_read(db) -> None:
    """#1589: a level, org admin, workspace admin. An organization named with no
    org admin and none of its workspaces is "<O> people" (its ``member`` here)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

    ws = "abi:nexus:organization/org-1/nexus:workspace/ws-1"
    org = "abi:nexus:organization/org-1"
    report = await import_users(
        db,
        [
            {
                "email": "viewer@example.com",
                "level": "viewer",
                "organizations": [{"slug": "org"}],
                "workspaces": [{"slug": "one"}],
            },
            {"email": "oadmin@example.com", "organizations": [{"slug": "org", "org_admin": True}]},
            {"email": "people@example.com", "organizations": [{"slug": "org"}]},
            {"email": "wadmin@example.com", "workspaces": [{"slug": "one", "admin": True}]},
        ],
    )
    await db.commit()
    ids = {u.email: u.id for u in (await db.execute(select(UserModel))).scalars()}

    assert await MEMBERSHIPS.role_at(ids["viewer@example.com"], ws) == "viewer"
    assert await MEMBERSHIPS.role_at(ids["viewer@example.com"], org) is None
    assert await MEMBERSHIPS.role_at(ids["oadmin@example.com"], org) == "admin"
    assert await MEMBERSHIPS.role_at(ids["people@example.com"], org) == "member"
    assert await MEMBERSHIPS.role_at(ids["wadmin@example.com"], ws) == "admin"
    assert report.organization_memberships_created == 2
    assert report.workspace_memberships_created == 2


@pytest.mark.asyncio
async def test_the_role_keys_of_before_are_read_with_a_warning(db, caplog) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

    with caplog.at_level("WARNING"):
        await import_users(
            db, [{"email": "old@example.com", "organizations": [{"slug": "org", "role": "owner"}]}]
        )
    await db.commit()
    old = (
        await db.execute(select(UserModel).where(UserModel.email == "old@example.com"))
    ).scalar_one()

    # Owner is no longer assigned: an org admin.
    assert await MEMBERSHIPS.role_at(old.id, "abi:nexus:organization/org-1") == "admin"
    assert "deprecated" in caplog.text and "org_admin" in caplog.text


@pytest.mark.asyncio
async def test_capabilities_are_joined_in_each_of_the_persons_organizations(db) -> None:
    report = await import_users(
        db,
        [
            {
                "email": "runner@example.com",
                "workspaces": [{"slug": "one"}],
                "capabilities": ["models_all", "workflow_runners", "nope"],
            }
        ],
    )

    # "Models · all" is the platform's; "Workflow runners" needs the organization's
    # access to bound it, which an organization recorded before #1585 has not.
    assert report.capabilities_joined == 1
    assert {m for m in report.missing if m.startswith("capability")} == {
        "capability workflow_runners of org-1: no organization access to bound it",
        "capability nope: not a capability group",
    }
