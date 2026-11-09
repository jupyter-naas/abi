from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    AuthService,
)


def _record(user_id: str, *, is_superadmin: bool = False) -> AuthUserRecord:
    return AuthUserRecord(
        id=user_id,
        email=f"{user_id}@example.com",
        name=user_id,
        created_at=datetime.utcnow(),
        is_superadmin=is_superadmin,
    )


@pytest.mark.asyncio
async def test_with_account_fallbacks_fills_empty_fields_from_member_profiles() -> None:
    from datetime import datetime as _dt

    from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord as _Record

    adapter = AsyncMock()
    adapter.list_member_profiles.return_value = [
        {
            "avatar": "/api/auth/avatar/user/u1/org?v=1",
            "organization": "Forvis Mazars",
            "job_title": None,
        },
        {"avatar": None, "organization": "Other", "job_title": "Partner"},
    ]
    service = AuthService(adapter=adapter)
    record = _Record(
        id="u1",
        email="a@b.c",
        name="A",
        created_at=_dt(2026, 1, 1),
        organization=None,
        job_title=None,
        avatar=None,
    )

    effective = await service.with_account_fallbacks(record)

    assert (effective.avatar, effective.organization, effective.job_title) == (
        "/api/auth/avatar/user/u1/org?v=1",
        "Forvis Mazars",
        "Partner",
    )


@pytest.mark.asyncio
async def test_with_account_fallbacks_skips_the_query_when_the_account_is_complete() -> None:
    from datetime import datetime as _dt

    from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord as _Record

    adapter = AsyncMock()
    service = AuthService(adapter=adapter)
    record = _Record(
        id="u1",
        email="a@b.c",
        name="A",
        created_at=_dt(2026, 1, 1),
        organization="Own",
        job_title="CTO",
        avatar="/me.png",
    )

    assert await service.with_account_fallbacks(record) is record
    adapter.list_member_profiles.assert_not_called()
