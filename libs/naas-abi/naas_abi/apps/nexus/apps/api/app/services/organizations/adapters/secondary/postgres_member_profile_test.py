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
    """alice belongs to two orgs, so a profile edit in one must not leak."""
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
                hashed_password="x",
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
            session.add(
                OrganizationMemberModel(
                    id=f"m-{org_id}",
                    organization_id=org_id,
                    user_id="alice",
                    role="member",
                    created_at=NOW,
                )
            )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_member_profile_falls_back_to_the_account_for_name_and_bio_only(
    db: AsyncSession,
) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    member = await adapter.get_organization_member(org_id="org-a", user_id="alice")

    assert member is not None
    assert (member.name, member.bio) == ("Alice", "Account bio")
    # Picture, organization and job title flow org -> account, never back.
    assert (member.avatar, member.organization, member.job_title) == (None, None, None)


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

    assert updated is not None
    assert (updated.name, updated.organization, updated.job_title, updated.bio) == (
        "Alice",  # the full name is always the account's
        "Acme",
        None,  # not set in this org: no account fallback
        "",  # an empty string blanks the field in this org only
    )
    other = await adapter.get_organization_member(org_id="org-b", user_id="alice")
    assert other is not None
    assert (other.name, other.organization, other.bio) == ("Alice", None, "Account bio")
    account = (await db.execute(select(UserModel).where(UserModel.id == "alice"))).scalar_one()
    assert (account.name, account.organization, account.bio) == (
        "Alice",
        "Freelance",
        "Account bio",
    )


@pytest.mark.asyncio
async def test_org_avatar_overrides_and_returns_the_previous_org_value(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    previous = await adapter.set_organization_member_avatar(
        org_id="org-a", user_id="alice", avatar="/api/auth/avatar/org-a.png"
    )
    assert previous is None  # the account avatar is not the org's to delete

    member = await adapter.get_organization_member(org_id="org-a", user_id="alice")
    assert member is not None and member.avatar == "/api/auth/avatar/org-a.png"

    previous = await adapter.set_organization_member_avatar(
        org_id="org-a", user_id="alice", avatar=None
    )
    assert previous == "/api/auth/avatar/org-a.png"
    member = await adapter.get_organization_member(org_id="org-a", user_id="alice")
    assert member is not None and member.avatar is None  # no account fallback


@pytest.mark.asyncio
async def test_listing_always_shows_the_account_name(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)
    await adapter.update_organization_member_profile(
        org_id="org-a",
        user_id="alice",
        name="Alice M.",
        organization=None,
        job_title=None,
        bio=None,
    )

    [in_a] = await adapter.list_organization_members(org_id="org-a")
    [in_b] = await adapter.list_organization_members(org_id="org-b")

    # The full name is always the account's, whatever an org stored.
    assert in_a.name == "Alice"
    assert in_b.name == "Alice"


@pytest.mark.asyncio
async def test_profile_update_returns_none_for_non_members(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    assert (
        await adapter.update_organization_member_profile(
            org_id="org-a", user_id="nobody", name="X", organization=None, job_title=None, bio=None
        )
        is None
    )
    assert (
        await adapter.set_organization_member_avatar(
            org_id="org-a", user_id="nobody", avatar="/x.png"
        )
        is None
    )


@pytest.mark.asyncio
async def test_details_split_account_and_organization_profile(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)
    await adapter.update_organization_member_profile(
        org_id="org-a", user_id="alice", name="Alice M.", organization=None, job_title=None, bio=""
    )

    details = await adapter.get_organization_member_details(org_id="org-a", user_id="alice")

    assert details is not None
    # As the members list shows them.
    assert (details.member.name, details.member.organization, details.member.bio) == (
        "Alice",
        None,
        "",
    )
    # The account, untouched by org edits.
    assert (details.account.name, details.account.organization, details.account.bio) == (
        "Alice",
        "Freelance",
        "Account bio",
    )
    assert details.account.email == "alice@example.com"
    assert details.account.created_at == NOW
    # Only what this organization set; None falls back to the account.
    assert (details.organization_profile.name, details.organization_profile.organization) == (
        "Alice M.",
        None,
    )
    assert details.organization_profile.bio == ""


@pytest.mark.asyncio
async def test_details_are_none_for_non_members(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    assert await adapter.get_organization_member_details(org_id="org-a", user_id="nobody") is None


@pytest.mark.asyncio
async def test_organization_only_fields_have_no_account_fallback(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    before = await adapter.get_organization_member(org_id="org-a", user_id="alice")
    assert (before.service_line, before.country, before.interest) == (None, None, None)

    updated = await adapter.update_organization_member_profile(
        org_id="org-a",
        user_id="alice",
        name=None,
        organization="Forvis Mazars",
        job_title=None,
        bio=None,
        service_line="Audit",
        country="France",
        interest="AI in audit",
    )

    assert (updated.organization, updated.service_line, updated.country, updated.interest) == (
        "Forvis Mazars",
        "Audit",
        "France",
        "AI in audit",
    )
    other = await adapter.get_organization_member(org_id="org-b", user_id="alice")
    assert (other.service_line, other.country) == (None, None)
