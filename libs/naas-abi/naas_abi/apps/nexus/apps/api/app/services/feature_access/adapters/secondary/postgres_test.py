"""``workspace_feature_policies``: made by its migration (again at every boot, as
every migration), read and replaced by the store."""

from __future__ import annotations

from pathlib import Path

import pytest
from naas_abi.apps.nexus.apps.api.app.services.feature_access.adapters.secondary.postgres import (  # noqa: E501
    SqlFeaturePolicyStore,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

MIGRATION = Path(__file__).parents[5] / "migrations" / "0074_workspace_feature_policies.sql"


@pytest.mark.asyncio
async def test_the_migration_runs_twice_and_the_store_records_one_policy_per_feature(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.sqlite'}")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE workspaces (id VARCHAR(255) PRIMARY KEY)"))
        for _ in range(2):
            await conn.execute(text(MIGRATION.read_text()))
    store = SqlFeaturePolicyStore(async_sessionmaker(engine, expire_on_commit=False))
    await store.put("alpha", "chat", "pol_1")
    await store.put("alpha", "files", "pol_2")
    await store.put("alpha", "chat", "pol_3")
    await store.put("beta", "chat", "pol_4")
    assert await store.policies("alpha") == {"chat": "pol_3", "files": "pol_2"}
    assert await store.managed_among(["pol_1", "pol_3", "pol_4", "pol_x"]) == {
        "pol_3": "chat",
        "pol_4": "chat",
    }
    assert await store.managed_among([]) == {}
    await engine.dispose()
