"""Nexus accounts name the people IAM knows by them: read from the ``users`` table."""

from __future__ import annotations

from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.models import UserModel
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.nexus_accounts import (
    SqlAccountNames,
)


@pytest.mark.asyncio
async def test_accounts_are_named_by_their_name_and_email(nexus_db) -> None:
    now = datetime(2026, 1, 1)
    async with nexus_db() as db:
        db.add(
            UserModel(id="u-1", email="ann@example.com", name="Ann", created_at=now, updated_at=now)
        )
        db.add(UserModel(id="u-2", email="bo@example.com", name="", created_at=now, updated_at=now))
        await db.commit()
    accounts = SqlAccountNames(nexus_db)

    assert await accounts.names_of(["u-1", "u-2", "gone"]) == {
        "u-1": ("Ann", "ann@example.com"),
        "u-2": (None, "bo@example.com"),
    }
    assert await accounts.names_of([]) == {}
