from __future__ import annotations

import json
from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store_test import MemoryStorage
from naas_abi.apps.nexus.apps.api.app.services.auth.user_drive_profile import (
    sync_user_drive_profile,
    sync_user_drive_profile_safely,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

NOW = datetime(2026, 1, 1)
T1 = datetime(2026, 10, 14, 9, 0, 0)
T2 = datetime(2026, 10, 14, 10, 0, 5)
ROOT = "naas_abi/my-drive/alice"
USER_DIR = f"{ROOT}/.settings/user"


@pytest_asyncio.fixture
async def db():
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
                hashed_password="secret-hash",
                bio="Account bio",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.add(
            OrganizationModel(
                id="org-fm",
                name="Forvis Mazars",
                slug="forvis-mazars",
                owner_id="alice",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.add(
            OrganizationMemberModel(
                id="m-1",
                organization_id="org-fm",
                user_id="alice",
                role="admin",
                created_at=NOW,
                organization_name="Forvis Mazars France",
                job_title="Partner",
                service_line="Audit",
                country="France",
                avatar="/api/auth/avatar/user/alice/org?v=abc",
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_writes_user_json_org_member_json_and_user_md(db: AsyncSession) -> None:
    storage = MemoryStorage()

    assert await sync_user_drive_profile(db, storage, "alice", T1) is True

    assert storage.paths() == {
        f"{USER_DIR}/user.json",
        f"{USER_DIR}/org_member.json",
        f"{ROOT}/.USER.md",
    }
    user = json.loads(storage.get_object(USER_DIR, "user.json"))["user"]
    assert (user["organization"], user["job_title"], user["avatar"]) == (None, None, None)
    org = json.loads(storage.get_object(USER_DIR, "org_member.json"))
    [membership] = org["memberships"]
    assert membership["organization_name"] == "Forvis Mazars"
    assert membership["role"] == "admin"
    assert membership["profile"]["service_line"] == "Audit"

    md = storage.get_object(ROOT, ".USER.md").decode()
    assert md.startswith("# Alice\n")
    # The account has none of its own: the member profile fills in.
    assert "- **Organization:** Forvis Mazars France (from organization profile)" in md
    assert "- **Job title:** Partner (from organization profile)" in md
    assert "- **Avatar:** /api/auth/avatar/user/alice/org?v=abc (from organization profile)" in md
    assert "### Forvis Mazars (Admin)" in md
    assert "- **Country:** France" in md
    assert "secret-hash" not in md


@pytest.mark.asyncio
async def test_account_values_win_and_changes_are_archived(db: AsyncSession) -> None:
    storage = MemoryStorage()
    await sync_user_drive_profile(db, storage, "alice", T1)
    user = (await db.execute(select(UserModel).where(UserModel.id == "alice"))).scalar_one()
    user.organization = "My own org"
    await db.flush()

    await sync_user_drive_profile(db, storage, "alice", T2)

    md = storage.get_object(ROOT, ".USER.md").decode()
    assert "- **Organization:** My own org\n" in md
    assert f"{USER_DIR}/archives/20261014T100005Z_user.json" in storage.paths()
    # org_member.json did not change, so it was not archived.
    assert not any(p.endswith("_org_member.json") for p in storage.paths())


@pytest.mark.asyncio
async def test_unknown_users_and_storage_failures_are_harmless(db: AsyncSession) -> None:
    class BrokenStorage(MemoryStorage):
        def put_object(self, prefix: str, key: str, content: bytes) -> None:
            raise RuntimeError("storage down")

    assert await sync_user_drive_profile(db, MemoryStorage(), "nobody", T1) is False
    await sync_user_drive_profile_safely(db, BrokenStorage(), "alice", T1)
