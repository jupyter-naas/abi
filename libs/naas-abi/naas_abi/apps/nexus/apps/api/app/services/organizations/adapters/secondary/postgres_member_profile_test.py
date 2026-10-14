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
                company="Freelance",
                role="Consultant",
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
async def test_member_profile_falls_back_to_the_account(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    member = await adapter.get_organization_member(org_id="org-a", user_id="alice")

    assert member is not None
    assert (member.name, member.company, member.job_title, member.bio) == (
        "Alice",
        "Freelance",
        "Consultant",
        "Account bio",
    )
    assert member.avatar == "/api/auth/avatar/alice.png"


@pytest.mark.asyncio
async def test_profile_edit_stays_in_its_organization(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    updated = await adapter.update_organization_member_profile(
        org_id="org-a",
        user_id="alice",
        name="Alice M.",
        company="Acme",
        job_title=None,
        bio="",
    )

    assert updated is not None
    assert (updated.name, updated.company, updated.job_title, updated.bio) == (
        "Alice M.",
        "Acme",
        "Consultant",  # untouched field keeps the account value
        "",  # an empty string blanks the field in this org only
    )
    other = await adapter.get_organization_member(org_id="org-b", user_id="alice")
    assert other is not None
    assert (other.name, other.company, other.bio) == ("Alice", "Freelance", "Account bio")
    account = (await db.execute(select(UserModel).where(UserModel.id == "alice"))).scalar_one()
    assert (account.name, account.company, account.bio) == ("Alice", "Freelance", "Account bio")


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
    assert member is not None and member.avatar == "/api/auth/avatar/alice.png"


@pytest.mark.asyncio
async def test_listing_uses_the_org_profile(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)
    await adapter.update_organization_member_profile(
        org_id="org-a", user_id="alice", name="Alice M.", company=None, job_title=None, bio=None
    )

    [in_a] = await adapter.list_organization_members(org_id="org-a")
    [in_b] = await adapter.list_organization_members(org_id="org-b")

    assert in_a.name == "Alice M."
    assert in_b.name == "Alice"


@pytest.mark.asyncio
async def test_profile_update_returns_none_for_non_members(db: AsyncSession) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    assert (
        await adapter.update_organization_member_profile(
            org_id="org-a", user_id="nobody", name="X", company=None, job_title=None, bio=None
        )
        is None
    )
    assert (
        await adapter.set_organization_member_avatar(
            org_id="org-a", user_id="nobody", avatar="/x.png"
        )
        is None
    )
