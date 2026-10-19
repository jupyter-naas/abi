"""Whether the caller is a platform admin is asked of IAM when it is wanted, and
only an IAM that is not there answers "no"."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary import (
    auth__primary_adapter__dependencies as dependencies,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.iam.runtime import IAMUnavailableError


def _record() -> AuthUserRecord:
    now = datetime(2026, 1, 1)
    return AuthUserRecord(
        id="u1",
        email="u1@example.com",
        name="U1",
        hashed_password="x",
        created_at=now,
    )


@pytest.mark.asyncio
async def test_a_request_does_not_ask_iam_whether_the_caller_is_an_admin(monkeypatch) -> None:
    asked = AsyncMock(return_value=True)
    monkeypatch.setattr(dependencies, "is_platform_admin", asked)
    credential = SimpleNamespace(user_id="u1", kind="session")
    monkeypatch.setattr(dependencies, "request_credential", AsyncMock(return_value=credential))
    service = SimpleNamespace(
        adapter=SimpleNamespace(get_user_by_id=AsyncMock(return_value=_record()))
    )

    user = await dependencies.get_current_user(SimpleNamespace(), None, service)  # type: ignore[arg-type]

    assert user is not None and user.id == "u1"
    asked.assert_not_called()


@pytest.mark.asyncio
async def test_the_account_routes_ask_for_it(monkeypatch) -> None:
    monkeypatch.setattr(dependencies, "is_platform_admin", AsyncMock(return_value=True))
    assert (await dependencies.to_signed_in_user(_record())).is_superadmin is True
    plain = dependencies.to_user_schema(_record())
    assert plain.is_superadmin is False
    assert (await dependencies.with_platform_role(plain)).is_superadmin is True


@pytest.mark.asyncio
async def test_without_iam_nobody_is_an_admin_but_other_failures_surface(monkeypatch) -> None:
    allowed = AsyncMock(side_effect=IAMUnavailableError("no IAM"))
    monkeypatch.setattr(dependencies.authz_module.AUTHZ, "allowed", allowed)
    assert await dependencies.is_platform_admin("u1") is False

    allowed.side_effect = RuntimeError("the broker is down")
    with pytest.raises(RuntimeError):
        await dependencies.is_platform_admin("u1")
