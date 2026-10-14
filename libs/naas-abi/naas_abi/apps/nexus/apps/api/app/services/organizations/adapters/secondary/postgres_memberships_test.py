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
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

NOW = datetime(2026, 1, 1)


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        for model in (UserModel, OrganizationModel, OrganizationMemberModel):
            await conn.run_sync(lambda sync, m=model: m.__table__.create(sync))
    async with AsyncSession(engine) as session:
        for uid in ("founder", "alice"):
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
        session.add_all(
            [
                OrganizationModel(
                    id="org-a",
                    name="Acme",
                    slug="acme",
                    owner_id="founder",
                    created_at=NOW,
                    updated_at=NOW,
                ),
                OrganizationModel(
                    id="org-b",
                    name="Beta",
                    slug="beta",
                    owner_id="founder",
                    created_at=NOW,
                    updated_at=NOW,
                ),
            ]
        )
        session.add_all(
            [
                OrganizationMemberModel(
                    id="m-1",
                    organization_id="org-a",
                    user_id="alice",
                    role="member",
                    created_at=NOW,
                ),
                OrganizationMemberModel(
                    id="m-2",
                    organization_id="org-a",
                    user_id="founder",
                    role="owner",
                    created_at=NOW,
                ),
            ]
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_lists_every_membership_including_owner_without_row(db) -> None:
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    memberships = await adapter.list_all_organization_memberships()

    assert [(m.user_id, m.organization_name, m.role) for m in memberships] == [
        ("alice", "Acme", "member"),
        ("founder", "Acme", "owner"),
        ("founder", "Beta", "owner"),
    ]
