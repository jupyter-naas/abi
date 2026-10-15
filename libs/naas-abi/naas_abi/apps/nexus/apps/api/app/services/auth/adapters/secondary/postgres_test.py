from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import MagicLinkTokenModel
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.secondary.postgres import (
    AuthSecondaryAdapterPostgres,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync: MagicLinkTokenModel.__table__.create(sync))
    async with AsyncSession(engine) as session:
        session.add(
            MagicLinkTokenModel(
                id="ml-1",
                user_id="user-1",
                token="hash",
                otp_attempts=0,
                expires_at=datetime(2999, 1, 1),
                used=False,
                created_at=datetime(2026, 1, 1),
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_otp_attempts_increment_in_the_database(db) -> None:
    adapter = AuthSecondaryAdapterPostgres(db=db)

    assert await adapter.increment_magic_link_otp_attempts("ml-1") == 1
    assert await adapter.increment_magic_link_otp_attempts("ml-1") == 2
    assert await adapter.increment_magic_link_otp_attempts("missing") == 0


@pytest_asyncio.fixture
async def org_db():
    from naas_abi.apps.nexus.apps.api.app.models import OrganizationMemberModel, WorkspaceModel

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync: WorkspaceModel.__table__.create(sync))
        await conn.run_sync(lambda sync: OrganizationMemberModel.__table__.create(sync))
    async with AsyncSession(engine) as session:
        now = datetime(2026, 1, 1)
        session.add_all(
            [
                WorkspaceModel(
                    id="ws-a",
                    name="A",
                    slug="a",
                    owner_id="owner",
                    organization_id="org-a",
                    created_at=now,
                    updated_at=now,
                ),
                WorkspaceModel(
                    id="ws-b",
                    name="B",
                    slug="b",
                    owner_id="owner",
                    organization_id="org-b",
                    created_at=now,
                    updated_at=now,
                ),
                WorkspaceModel(
                    id="ws-none",
                    name="N",
                    slug="n",
                    owner_id="owner",
                    organization_id=None,
                    created_at=now,
                    updated_at=now,
                ),
                OrganizationMemberModel(
                    id="m-a",
                    organization_id="org-a",
                    user_id="user-1",
                    role="member",
                    created_at=now,
                    organization_name="Acme",
                    job_title="CTO",
                    bio="Bikes.",
                ),
                OrganizationMemberModel(
                    id="m-b",
                    organization_id="org-b",
                    user_id="user-1",
                    role="member",
                    created_at=now,
                    organization_name="Beta Corp",
                ),
            ]
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_workspace_member_profile_is_the_one_of_the_workspace_organization(org_db) -> None:
    adapter = AuthSecondaryAdapterPostgres(db=org_db)

    assert await adapter.get_workspace_member_profile("user-1", "ws-a") == {
        "organization": "Acme",
        "job_title": "CTO",
        "bio": "Bikes.",
    }
    assert await adapter.get_workspace_member_profile("user-1", "ws-b") == {
        "organization": "Beta Corp",
        "job_title": None,
        "bio": None,
    }


@pytest.mark.asyncio
async def test_workspace_member_profile_is_none_outside_an_organization(org_db) -> None:
    adapter = AuthSecondaryAdapterPostgres(db=org_db)

    assert await adapter.get_workspace_member_profile("user-1", "ws-none") is None
    assert await adapter.get_workspace_member_profile("user-2", "ws-a") is None
    assert await adapter.get_workspace_member_profile("user-1", "missing") is None
