from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    AuthService,
    SuperadminChangeError,
    UserNotFoundError,
)


def _record(user_id: str, *, is_superadmin: bool = False) -> AuthUserRecord:
    return AuthUserRecord(
        id=user_id,
        email=f"{user_id}@example.com",
        name=user_id,
        created_at=datetime.utcnow(),
        is_superadmin=is_superadmin,
    )


class Memberships:
    """The platform administrators IAM holds."""

    def __init__(self, admins: set[str]) -> None:
        self.admins = set(admins)
        self.changes: list[tuple[str, bool, str | None]] = []

    async def platform_admins(self) -> set[str]:
        return set(self.admins)

    async def set_platform_admin(self, user_id: str, on: bool, *, by=None) -> None:
        self.changes.append((user_id, on, by))
        (self.admins.add if on else self.admins.discard)(user_id)


@pytest.mark.asyncio
async def test_set_superadmin_attaches_the_platform_admin_role_as_the_actor() -> None:
    adapter = AsyncMock()
    adapter.get_user_by_id.return_value = _record("user-2")
    iam = Memberships({"user-1"})
    service = AuthService(adapter=adapter, memberships=iam)  # type: ignore[arg-type]

    updated = await service.set_superadmin(actor_id="user-1", user_id="user-2", is_superadmin=True)

    assert updated.is_superadmin is True
    assert iam.changes == [("user-2", True, "user-1")]
    assert iam.admins == {"user-1", "user-2"}
    adapter.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_superadmin_refuses_self_demotion() -> None:
    adapter = AsyncMock()
    adapter.get_user_by_id.return_value = _record("user-1")
    iam = Memberships({"user-1", "user-2"})
    service = AuthService(adapter=adapter, memberships=iam)  # type: ignore[arg-type]

    with pytest.raises(SuperadminChangeError, match="cannot_demote_self"):
        await service.set_superadmin(actor_id="user-1", user_id="user-1", is_superadmin=False)
    assert iam.changes == []


@pytest.mark.asyncio
async def test_set_superadmin_refuses_to_demote_the_last_superadmin() -> None:
    adapter = AsyncMock()
    adapter.get_user_by_id.return_value = _record("user-2")
    iam = Memberships({"user-2"})
    service = AuthService(adapter=adapter, memberships=iam)  # type: ignore[arg-type]

    with pytest.raises(SuperadminChangeError, match="last_superadmin"):
        await service.set_superadmin(actor_id="user-1", user_id="user-2", is_superadmin=False)
    assert iam.changes == []


@pytest.mark.asyncio
async def test_set_superadmin_unknown_user() -> None:
    adapter = AsyncMock()
    adapter.get_user_by_id.return_value = None
    service = AuthService(adapter=adapter, memberships=Memberships(set()))  # type: ignore[arg-type]

    with pytest.raises(UserNotFoundError):
        await service.set_superadmin(actor_id="user-1", user_id="ghost", is_superadmin=True)


@pytest.mark.asyncio
async def test_the_account_list_shows_who_iam_holds_as_a_platform_admin() -> None:
    adapter = AsyncMock()
    # The stored flag is not the truth: IAM's attachment is.
    adapter.list_users.return_value = [
        _record("user-1", is_superadmin=False),
        _record("user-2", is_superadmin=True),
    ]
    service = AuthService(adapter=adapter, memberships=Memberships({"user-1"}))  # type: ignore[arg-type]

    users = await service.list_users()

    assert [(user.id, user.is_superadmin) for user in users] == [
        ("user-1", True),
        ("user-2", False),
    ]


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
