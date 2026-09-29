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
