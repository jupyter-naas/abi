from __future__ import annotations

import json
from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core.workspaces_import import (
    import_workspaces,
    load_entries,
)
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

NOW = datetime(2026, 1, 1)
TABLES = (UserModel, OrganizationModel, WorkspaceModel)


@pytest.fixture(autouse=True)
def iam(nexus_iam):
    """Roles are IAM's: the organization and the leads it knows."""
    nexus_iam.org("org-1")
    nexus_iam.user("lead")
    return nexus_iam


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        for model in TABLES:
            await conn.run_sync(lambda sync, m=model: m.__table__.create(sync))
    async with AsyncSession(engine) as session:
        for uid in ("founder", "lead"):
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
        session.add_all(
            [
                # Seeded from a config without a name: named after its slug.
                WorkspaceModel(
                    id="ws-axa",
                    name="axa",
                    slug="axa",
                    owner_id="founder",
                    organization_id="org-1",
                    created_at=NOW,
                    updated_at=NOW,
                ),
                # Renamed and regrouped in the app, overrides saved in the app.
                WorkspaceModel(
                    id="ws-edf",
                    name="EDF (renamed)",
                    slug="edf",
                    owner_id="founder",
                    organization_id="org-1",
                    workspace_group="Energy",
                    feature_overrides='{"maps": true}',
                    created_at=NOW,
                    updated_at=NOW,
                ),
            ]
        )
        await session.commit()
        yield session
    await engine.dispose()


ENTRIES = [
    {
        "slug": "axa",
        "organization": "org",
        "name": "AXA",
        "group": "Key Accounts",
        "logo_url": "src/external/axa/assets/public/axa-logo.png",
        "feature_overrides": {"maps": False, "graph": True},
    },
    {
        "slug": "edf",
        "organization": "org",
        "name": "EDF",
        "group": "Key Accounts",
        "feature_overrides": {"maps": False},
    },
    {
        "slug": "new-one",
        "organization": "org",
        "name": "New One",
        "owner_email": "lead@example.com",
        "primary_color": "#3b82f6",
    },
    {"slug": "orphan", "organization": "nope", "name": "Orphan"},
]


async def _ws(db: AsyncSession, slug: str) -> WorkspaceModel | None:
    return (
        await db.execute(select(WorkspaceModel).where(WorkspaceModel.slug == slug))
    ).scalar_one_or_none()


@pytest.mark.asyncio
async def test_fills_a_slug_named_workspace_with_the_snapshot_values(db) -> None:
    await import_workspaces(db, ENTRIES)

    axa = await _ws(db, "axa")
    assert (axa.name, axa.workspace_group, axa.logo_url) == (
        "AXA",
        "Key Accounts",
        "src/external/axa/assets/public/axa-logo.png",
    )
    assert json.loads(axa.feature_overrides) == {"graph": True, "maps": False}


@pytest.mark.asyncio
async def test_keeps_values_changed_in_the_app(db) -> None:
    await import_workspaces(db, ENTRIES)

    edf = await _ws(db, "edf")
    assert (edf.name, edf.workspace_group) == ("EDF (renamed)", "Energy")
    assert json.loads(edf.feature_overrides) == {"maps": True}


@pytest.mark.asyncio
async def test_creates_missing_workspaces_and_reports_unknown_organizations(db) -> None:
    report = await import_workspaces(db, ENTRIES)

    created = await _ws(db, "new-one")
    assert (created.name, created.owner_id, created.primary_color) == (
        "New One",
        "lead",
        "#3b82f6",
    )
    # The owner role is IAM's attachment, at the new workspace's scope.
    assert await MEMBERSHIPS.role_at("lead", f"abi:org-1:{created.id}") == "owner"
    assert await _ws(db, "orphan") is None
    # EDF has nothing empty to fill: only AXA counts as updated.
    assert (report.workspaces_created, report.workspaces_updated) == (1, 1)
    assert "organization nope" in report.missing


@pytest.mark.asyncio
async def test_a_dry_run_leaves_iam_alone(db) -> None:
    report = await import_workspaces(db, ENTRIES, apply=False)
    created = (await _ws(db, "new-one")).id
    await db.rollback()

    assert report.created_ids == [created] and report.overrides_saved
    assert await MEMBERSHIPS.role_at("lead", f"abi:org-1:{created}") is None


@pytest.mark.asyncio
async def test_a_second_run_changes_nothing(db) -> None:
    await import_workspaces(db, ENTRIES)

    again = await import_workspaces(db, ENTRIES)

    assert (again.workspaces_created, again.workspaces_updated) == (0, 0)


def test_load_entries_reads_the_workspaces_list(tmp_path) -> None:
    path = tmp_path / "config.workspaces.yaml"
    path.write_text("workspaces:\n  - slug: axa\n    name: AXA\n")

    assert load_entries(path) == [{"slug": "axa", "name": "AXA"}]
