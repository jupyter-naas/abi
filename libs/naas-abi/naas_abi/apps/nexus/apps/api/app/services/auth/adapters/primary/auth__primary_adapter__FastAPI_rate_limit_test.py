"""Every credential endpoint is rate-limited, per IP and per account."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary import (
    auth__primary_adapter__FastAPI as auth_api,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    ForgotPasswordRequest,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    OtpVerifyRequest,
    ResetPasswordRequest,
    UserCreate,
    UserLogin,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    InvalidCredentialsError,
    InvalidOtpError,
)

EMAIL = "victim@example.com"


class Limiter:
    def __init__(self) -> None:
        self.blocked = False
        self.block_prefix = ""
        self.checked: list[tuple[str, str]] = []
        self.recorded: list[tuple[str, str]] = []

    async def ensure_under_limit(self, identifier: str, endpoint: str, limit: int) -> None:
        self.checked.append((identifier, endpoint))
        if self.blocked and identifier.startswith(self.block_prefix):
            raise HTTPException(status_code=429, detail="Too many attempts")

    async def record_attempt(self, identifier: str, endpoint: str) -> None:
        self.recorded.append((identifier, endpoint))


@pytest.fixture
def limiter(monkeypatch: pytest.MonkeyPatch) -> Limiter:
    limiter = Limiter()
    monkeypatch.setattr(auth_api, "ensure_under_limit", limiter.ensure_under_limit)
    monkeypatch.setattr(auth_api, "record_attempt", limiter.record_attempt)
    monkeypatch.setattr(auth_api, "log_login", AsyncMock())
    monkeypatch.setattr(auth_api, "log_register", AsyncMock())
    monkeypatch.setattr(settings, "auth_password_enabled", True)
    monkeypatch.setattr(settings, "auth_signup_enabled", True)
    return limiter


def _request() -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host="203.0.113.7"), headers={})


def _calls(service: AsyncMock):
    request = _request()
    return {
        "register": lambda: auth_api.register(
            UserCreate(email=EMAIL, password="a-long-password", name="V"), request, service
        ),
        "login": lambda: auth_api.login(UserLogin(email=EMAIL, password="guess"), request, service),
        "token": lambda: auth_api.login_for_access_token(
            request, SimpleNamespace(username=EMAIL, password="guess"), service
        ),
        "magic-link/request": lambda: auth_api.request_magic_link(
            request, MagicLinkRequest(email=EMAIL), service, None
        ),
        "magic-link/verify": lambda: auth_api.verify_magic_link(
            request, MagicLinkVerifyRequest(token="t"), service
        ),
        "otp/verify": lambda: auth_api.verify_otp(
            request, OtpVerifyRequest(email=EMAIL, code="123456"), service
        ),
        "forgot-password": lambda: auth_api.forgot_password(
            request, ForgotPasswordRequest(email=EMAIL), service
        ),
        "reset-password": lambda: auth_api.reset_password(
            request, ResetPasswordRequest(token="t", new_password="a-long-password"), service
        ),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint",
    [
        "register",
        "login",
        "token",
        "magic-link/request",
        "magic-link/verify",
        "otp/verify",
        "forgot-password",
        "reset-password",
    ],
)
async def test_a_blocked_caller_never_reaches_the_service(limiter: Limiter, endpoint: str) -> None:
    limiter.blocked = True
    service = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await _calls(service)[endpoint]()

    assert exc_info.value.status_code == 429
    assert service.method_calls == []
    assert ("ip:203.0.113.7", f"/api/auth/{endpoint}") in limiter.checked


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["login", "token", "magic-link/request", "otp/verify"])
async def test_account_endpoints_are_also_limited_per_email(limiter: Limiter, endpoint: str) -> None:
    limiter.blocked = True
    limiter.block_prefix = "email:"

    with pytest.raises(HTTPException):
        await _calls(AsyncMock())[endpoint]()

    assert (f"email:{EMAIL}", f"/api/auth/{endpoint}") in limiter.checked


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["login", "token"])
async def test_a_failed_password_counts_against_ip_and_account(
    limiter: Limiter, endpoint: str
) -> None:
    service = AsyncMock()
    service.login_user.side_effect = InvalidCredentialsError(reason="invalid_password")
    service.create_oauth_access_token.side_effect = InvalidCredentialsError(reason="invalid")

    with pytest.raises(HTTPException) as exc_info:
        await _calls(service)[endpoint]()

    assert exc_info.value.status_code == 401
    assert set(limiter.recorded) == {
        ("ip:203.0.113.7", f"/api/auth/{endpoint}"),
        (f"email:{EMAIL}", f"/api/auth/{endpoint}"),
    }


@pytest.mark.asyncio
async def test_a_successful_login_is_not_counted(limiter: Limiter, monkeypatch) -> None:
    monkeypatch.setattr(auth_api, "to_user_schema", lambda user: user)
    monkeypatch.setattr(auth_api, "AuthResponse", lambda **kwargs: kwargs)
    service = AsyncMock()
    service.login_user.return_value = (
        SimpleNamespace(id="user-1"),
        SimpleNamespace(access_token="a", refresh_token="r", expires_in=1),
    )

    await _calls(service)["login"]()

    assert limiter.recorded == []


@pytest.mark.asyncio
async def test_a_wrong_code_counts_against_ip_and_account(limiter: Limiter) -> None:
    service = AsyncMock()
    service.verify_otp.side_effect = InvalidOtpError()

    with pytest.raises(HTTPException):
        await _calls(service)["otp/verify"]()

    assert (f"email:{EMAIL}", "/api/auth/otp/verify") in limiter.recorded


@pytest.mark.asyncio
async def test_every_code_request_counts_so_codes_cannot_be_farmed(limiter: Limiter) -> None:
    service = AsyncMock()
    service.request_magic_link.return_value = None

    await _calls(service)["magic-link/request"]()

    assert set(limiter.recorded) == {
        ("ip:203.0.113.7", "/api/auth/magic-link/request"),
        (f"email:{EMAIL}", "/api/auth/magic-link/request"),
    }


@pytest.mark.asyncio
async def test_register_is_refused_when_signup_is_disabled(limiter: Limiter) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import SignupDisabledError

    service = AsyncMock()
    service.register_user.side_effect = SignupDisabledError()

    with pytest.raises(HTTPException) as exc_info:
        await _calls(service)["register"]()

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_auth_config_tells_the_ui_whether_signup_is_open(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_signup_enabled", False)

    assert (await auth_api.get_auth_config())["signup_enabled"] is False
