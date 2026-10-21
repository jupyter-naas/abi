from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

NOW = datetime(2026, 1, 1)


@pytest_asyncio.fixture
async def db():
    """alice is in two orgs, so a profile edit in one must not leak. Who holds a role
    is IAM's: the table keeps only what an organization set for a person."""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        for model in (UserModel, OrganizationModel, OrganizationMemberModel):
            await conn.run_sync(lambda sync, m=model: m.__table__.create(sync))
    async with AsyncSession(engine) as session:
        session.add(
            UserModel(
                id="alice",
                email="alice@example.com",
                name="Alice",
                avatar="/api/auth/avatar/alice.png",
                organization="Freelance",
                job_title="Consultant",
                bio="Account bio",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        for org_id in ("org-a", "org-b"):
            session.add(
                OrganizationModel(
                    id=org_id,
                    name=org_id,
                    slug=org_id,
                    owner_id="alice",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_a_person_has_no_profile_until_an_organization_sets_one(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    assert await adapter.get_organization_member_profile("org-a", "alice") is None
    assert await adapter.list_organization_member_profiles("org-a") == {}


@pytest.mark.asyncio
async def test_profile_edit_stays_in_its_organization(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    updated = await adapter.update_organization_member_profile(
        org_id="org-a",
        user_id="alice",
        name="Alice M.",
        organization="Acme",
        job_title=None,
        bio="",
    )

    # None leaves a field unset (no account fallback in the profile itself); "" blanks it.
    assert (updated.name, updated.organization, updated.job_title, updated.bio) == (
        "Alice M.",
        "Acme",
        None,
        "",
    )
    assert await adapter.get_organization_member_profile("org-b", "alice") is None
    account = (await db.execute(select(UserModel).where(UserModel.id == "alice"))).scalar_one()
    assert (account.name, account.organization, account.bio) == (
        "Alice",
        "Freelance",
        "Account bio",
    )


@pytest.mark.asyncio
async def test_a_second_edit_changes_only_what_it_names(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)
    await adapter.update_organization_member_profile(
        org_id="org-a",
        user_id="alice",
        name=None,
        organization="Forvis Mazars",
        job_title="Partner",
        bio=None,
        service_line="Audit",
        country="France",
        interest="AI in audit",
    )

    updated = await adapter.update_organization_member_profile(
        org_id="org-a",
        user_id="alice",
        name=None,
        organization=None,
        job_title="Director",
        bio=None,
    )

    assert (updated.organization, updated.job_title, updated.service_line) == (
        "Forvis Mazars",
        "Director",
        "Audit",
    )
    rows = (await db.execute(select(OrganizationMemberModel))).scalars().all()
    assert len(rows) == 1  # one row per organization and person, made on the first edit


@pytest.mark.asyncio
async def test_org_avatar_returns_the_previous_org_value(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    previous = await adapter.set_organization_member_avatar(
        org_id="org-a", user_id="alice", avatar="/api/auth/avatar/org-a.png"
    )
    assert previous is None  # the account avatar is not the org's to delete
    profile = await adapter.get_organization_member_profile("org-a", "alice")
    assert profile is not None and profile.avatar == "/api/auth/avatar/org-a.png"

    previous = await adapter.set_organization_member_avatar(
        org_id="org-a", user_id="alice", avatar=None
    )
    assert previous == "/api/auth/avatar/org-a.png"
    profile = await adapter.get_organization_member_profile("org-a", "alice")
    assert profile is not None and profile.avatar is None  # no account fallback


@pytest.mark.asyncio
async def test_profiles_are_listed_per_organization(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)
    await adapter.update_organization_member_profile(
        org_id="org-a", user_id="alice", name=None, organization="Acme", job_title=None, bio=None
    )

    in_a = await adapter.list_organization_member_profiles("org-a")
    in_b = await adapter.list_organization_member_profiles("org-b")

    assert {user_id: profile.organization for user_id, profile in in_a.items()} == {"alice": "Acme"}
    assert in_b == {}


@pytest.mark.asyncio
async def test_the_account_is_read_apart_from_the_profile(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    account = await adapter.get_member_account("alice")

    assert account is not None
    assert (account.name, account.organization, account.bio) == (
        "Alice",
        "Freelance",
        "Account bio",
    )
    assert (account.email, account.created_at) == ("alice@example.com", NOW)
    assert await adapter.get_member_account("nobody") is None
