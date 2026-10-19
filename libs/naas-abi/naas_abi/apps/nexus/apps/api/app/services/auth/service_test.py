from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.auth.port import (
    AuthUserRecord,
    MagicLinkTokenRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    AuthService,
    EmailChangeNotAllowedError,
    InvalidMagicLinkError,
    InvalidOtpError,
    PasswordAuthenticationDisabledError,
)
from naas_abi.apps.nexus.apps.api.app.services.refresh_token import hash_otp_code, hash_token


@pytest.mark.asyncio
async def test_forgot_password_stores_hashed_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_password_enabled", True)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )

    service = AuthService(adapter=adapter)
    raw_token = await service.forgot_password("USER@EXAMPLE.COM")

    assert raw_token is not None
    assert raw_token != ""
    adapter.create_password_reset_token.assert_awaited_once()
    stored_token = adapter.create_password_reset_token.await_args.kwargs["token"]
    assert stored_token == hash_token(raw_token)
    assert stored_token != raw_token


@pytest.mark.asyncio
async def test_forgot_password_for_unknown_user_does_not_store_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_password_enabled", True)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    service = AuthService(adapter=adapter)

    token = await service.forgot_password("unknown@example.com")

    assert token is None
    adapter.create_password_reset_token.assert_not_called()
    adapter.commit.assert_not_called()


@pytest.mark.asyncio
async def test_request_magic_link_stores_hashed_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "magic_link_max_active", 5)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    challenge = await service.request_magic_link("USER@EXAMPLE.COM")

    assert challenge
    assert len(challenge.otp_code) == settings.otp_code_length
    adapter.mark_unused_magic_link_tokens_used.assert_awaited_once_with(
        "user-1",
        keep_latest_unused=4,
    )
    adapter.create_magic_link_token.assert_awaited_once()
    stored_token = adapter.create_magic_link_token.await_args.kwargs["token"]
    assert stored_token == hash_token(challenge.token)
    assert stored_token != challenge.token
    stored_otp = adapter.create_magic_link_token.await_args.kwargs["otp_code_hash"]
    assert stored_otp == hash_otp_code(challenge.otp_code)
    assert stored_otp != challenge.otp_code


@pytest.mark.asyncio
async def test_request_magic_link_with_non_positive_max_active_invalidates_all(monkeypatch) -> None:
    monkeypatch.setattr(settings, "magic_link_max_active", 0)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    challenge = await service.request_magic_link("user@example.com")

    assert challenge
    adapter.mark_unused_magic_link_tokens_used.assert_awaited_once_with(
        "user-1",
        keep_latest_unused=0,
    )


@pytest.mark.asyncio
async def test_request_magic_link_for_unknown_user_does_not_create_account(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "magic_link_allow_signup", False)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    service = AuthService(adapter=adapter)

    challenge = await service.request_magic_link("unknown@example.com")

    assert challenge is None
    adapter.create_user.assert_not_called()
    adapter.create_user_with_default_workspace.assert_not_called()
    adapter.create_magic_link_token.assert_not_called()
    adapter.commit.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_user_for_invite_creates_user_without_workspace() -> None:
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    adapter.create_user.return_value = AuthUserRecord(
        id="user-new",
        email="new@example.com",
        name="New",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    user, created = await service.ensure_user_for_invite("NEW@example.com", name="Emma Petit")

    assert created is True
    assert user.id == "user-new"
    adapter.create_user.assert_awaited_once()
    assert adapter.create_user.await_args.kwargs["name"] == "Emma Petit"
    adapter.create_user_with_default_workspace.assert_not_called()
    adapter.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_user_for_invite_returns_existing_account() -> None:
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    user, created = await service.ensure_user_for_invite("user@example.com")

    assert created is False
    assert user.id == "user-1"
    adapter.create_user.assert_not_called()
    adapter.create_user_with_default_workspace.assert_not_called()


class _Memberships:
    """What a signup asks of IAM: records the calls, can be made to fail."""

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple] = []
        self.fail = fail

    async def register_workspace(self, org_id, workspace_id):
        self.calls.append(("register_workspace", org_id, workspace_id))
        return f"abi:_none:{workspace_id}"

    async def grant(self, user_id, role, scope, **_):
        if self.fail:
            raise RuntimeError("IAM is down")
        self.calls.append(("grant", user_id, role, scope))

    async def drop_scope(self, org_id, workspace_id):
        self.calls.append(("drop_scope", org_id, workspace_id))


@pytest.mark.asyncio
async def test_a_signup_whose_owner_cannot_be_set_forgets_the_scope(monkeypatch) -> None:
    monkeypatch.setattr(settings, "magic_link_allow_signup", True)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    adapter.create_user_with_default_workspace.return_value = AuthUserRecord(
        id="user-2",
        email="unknown@example.com",
        name="Unknown",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    memberships = _Memberships(fail=True)
    service = AuthService(adapter=adapter, memberships=memberships)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError):
        await service.request_magic_link("unknown@example.com")

    assert memberships.calls[-1] == ("drop_scope", None, "user-2")
    adapter.commit.assert_not_called()


@pytest.mark.asyncio
async def test_request_magic_link_public_signup_creates_default_workspace(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "magic_link_allow_signup", True)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    adapter.create_user_with_default_workspace.return_value = AuthUserRecord(
        id="user-2",
        email="unknown@example.com",
        name="Unknown",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    memberships = _Memberships()
    service = AuthService(adapter=adapter, memberships=memberships)  # type: ignore[arg-type]

    challenge = await service.request_magic_link("unknown@example.com")

    assert challenge
    # The personal workspace is IAM's from the first request: scope, owner, placements.
    assert memberships.calls == [
        ("register_workspace", None, "user-2"),
        ("grant", "user-2", "owner", "abi:_none:user-2"),
    ]
    adapter.place_workspace.assert_awaited_once_with("user-2")
    adapter.create_user_with_default_workspace.assert_awaited_once()
    assert adapter.create_user_with_default_workspace.await_args.kwargs["name"] == "Unknown"
    adapter.create_user.assert_not_called()
    adapter.create_magic_link_token.assert_awaited_once()
    adapter.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_magic_link_create_if_missing_true_skips_workspace(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "magic_link_allow_signup", False)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = None
    adapter.create_user.return_value = AuthUserRecord(
        id="user-3",
        email="invitee@example.com",
        name="Invitee",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    challenge = await service.request_magic_link("invitee@example.com", create_if_missing=True)

    assert challenge
    adapter.create_user.assert_awaited_once()
    adapter.create_user_with_default_workspace.assert_not_called()
    adapter.create_magic_link_token.assert_awaited_once()


@pytest.mark.asyncio
async def test_verify_magic_link_rejects_unknown_token() -> None:
    adapter = AsyncMock()
    adapter.get_magic_link_token.return_value = None
    service = AuthService(adapter=adapter)

    with pytest.raises(InvalidMagicLinkError):
        await service.verify_magic_link("token", user_agent=None, ip_address=None)


@pytest.mark.asyncio
async def test_password_login_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_password_enabled", False)
    adapter = AsyncMock()
    service = AuthService(adapter=adapter)

    with pytest.raises(PasswordAuthenticationDisabledError):
        await service.login_user("user@example.com", "pass", None, None)


@pytest.mark.asyncio
async def test_verify_otp_accepts_valid_code(monkeypatch) -> None:
    monkeypatch.setattr(settings, "otp_code_length", 6)
    monkeypatch.setattr(settings, "otp_max_attempts", 5)
    code = "482913"
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    adapter.list_unused_magic_links_for_user.return_value = [
        MagicLinkTokenRecord(
            id="ml-1",
            user_id="user-1",
            token="link-hash",
            expires_at=datetime.utcnow().replace(year=2099),
            used=False,
            created_at=datetime.utcnow(),
            otp_code_hash=hash_otp_code(code),
            otp_attempts=0,
        )
    ]
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.auth.service.create_refresh_token",
        AsyncMock(return_value="refresh"),
    )
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.auth.service.create_access_token",
        lambda data, expires_delta=None: ("access", "jti"),
    )
    service = AuthService(adapter=adapter)

    user, tokens = await service.verify_otp(
        email="USER@example.com",
        code=code,
        user_agent=None,
        ip_address=None,
    )

    assert user.id == "user-1"
    assert tokens.access_token == "access"
    adapter.mark_magic_link_token_used.assert_awaited_with("ml-1")


@pytest.mark.asyncio
async def test_verify_otp_matches_older_challenge_when_newer_unused_exists(
    monkeypatch,
) -> None:
    """Recreate/retry can leave a newer unused row that shadows the emailed OTP."""
    monkeypatch.setattr(settings, "otp_code_length", 6)
    monkeypatch.setattr(settings, "otp_max_attempts", 5)
    emailed_code = "926740"
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    adapter.list_unused_magic_links_for_user.return_value = [
        MagicLinkTokenRecord(
            id="ml-newer",
            user_id="user-1",
            token="newer-hash",
            expires_at=datetime.utcnow().replace(year=2099),
            used=False,
            created_at=datetime.utcnow(),
            otp_code_hash=hash_otp_code("111111"),
            otp_attempts=0,
        ),
        MagicLinkTokenRecord(
            id="ml-emailed",
            user_id="user-1",
            token="emailed-hash",
            expires_at=datetime.utcnow().replace(year=2099),
            used=False,
            created_at=datetime.utcnow(),
            otp_code_hash=hash_otp_code(emailed_code),
            otp_attempts=0,
        ),
    ]
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.auth.service.create_refresh_token",
        AsyncMock(return_value="refresh"),
    )
    monkeypatch.setattr(
        "naas_abi.apps.nexus.apps.api.app.services.auth.service.create_access_token",
        lambda data, expires_delta=None: ("access", "jti"),
    )
    service = AuthService(adapter=adapter)

    user, tokens = await service.verify_otp(
        email="user@example.com",
        code=emailed_code,
        user_agent=None,
        ip_address=None,
    )

    assert user.id == "user-1"
    assert tokens.access_token == "access"
    adapter.mark_magic_link_token_used.assert_awaited_with("ml-emailed")
    adapter.increment_magic_link_otp_attempts.assert_not_awaited()


@pytest.mark.asyncio
async def test_verify_otp_rejects_wrong_code_and_increments(monkeypatch) -> None:
    monkeypatch.setattr(settings, "otp_code_length", 6)
    monkeypatch.setattr(settings, "otp_max_attempts", 5)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    adapter.list_unused_magic_links_for_user.return_value = [
        MagicLinkTokenRecord(
            id="ml-1",
            user_id="user-1",
            token="link-hash",
            expires_at=datetime.utcnow().replace(year=2099),
            used=False,
            created_at=datetime.utcnow(),
            otp_code_hash=hash_otp_code("111111"),
            otp_attempts=0,
        )
    ]
    adapter.increment_magic_link_otp_attempts.return_value = 1
    service = AuthService(adapter=adapter)

    with pytest.raises(InvalidOtpError):
        await service.verify_otp(
            email="user@example.com",
            code="000000",
            user_agent=None,
            ip_address=None,
        )

    adapter.increment_magic_link_otp_attempts.assert_awaited_once_with("ml-1")
    adapter.mark_magic_link_token_used.assert_not_awaited()


def _user_with_password(password: str) -> AuthUserRecord:
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import get_password_hash

    return AuthUserRecord(
        id="user-1",
        email="admin@example.com",
        name="Admin",
        hashed_password=get_password_hash(password),
        created_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("password", ["Admin1234!", "admin"])
async def test_login_refuses_a_default_password_even_when_it_matches(
    monkeypatch, password: str
) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
        InvalidCredentialsError,
    )

    monkeypatch.setattr(settings, "auth_password_enabled", True)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = _user_with_password(password)
    service = AuthService(adapter=adapter)

    with pytest.raises(InvalidCredentialsError):
        await service.login_user("admin@example.com", password, None, None)
    with pytest.raises(InvalidCredentialsError):
        await service.create_oauth_access_token("admin@example.com", password)


@pytest.mark.asyncio
async def test_register_rejects_a_default_password(monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
        DefaultPasswordNotAllowedError,
    )

    monkeypatch.setattr(settings, "auth_password_enabled", True)
    monkeypatch.setattr(settings, "auth_signup_enabled", True)
    adapter = AsyncMock()
    adapter.user_exists_with_email.return_value = False
    service = AuthService(adapter=adapter)

    with pytest.raises(DefaultPasswordNotAllowedError):
        await service.register_user("new@example.com", "Admin1234!", "New", None, None)
    adapter.create_user_with_default_workspace.assert_not_called()


@pytest.mark.asyncio
async def test_change_and_reset_reject_a_default_password(monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.port import PasswordResetTokenRecord
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
        DefaultPasswordNotAllowedError,
    )

    monkeypatch.setattr(settings, "auth_password_enabled", True)
    adapter = AsyncMock()
    adapter.get_user_by_id.return_value = _user_with_password("a-real-current-password")
    adapter.get_password_reset_token.return_value = PasswordResetTokenRecord(
        id="reset-1",
        user_id="user-1",
        token="hashed",
        expires_at=datetime(2999, 1, 1),
        used=False,
        created_at=datetime.utcnow(),
    )
    service = AuthService(adapter=adapter)

    with pytest.raises(DefaultPasswordNotAllowedError):
        await service.change_password("user-1", "a-real-current-password", "admin", None, None)
    with pytest.raises(DefaultPasswordNotAllowedError):
        await service.reset_password("raw-token", "Admin1234!")
    adapter.update_user_password.assert_not_called()


@pytest.mark.asyncio
async def test_register_is_refused_when_signup_is_disabled(monkeypatch) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import SignupDisabledError

    monkeypatch.setattr(settings, "auth_password_enabled", True)
    monkeypatch.setattr(settings, "auth_signup_enabled", False)
    adapter = AsyncMock()
    service = AuthService(adapter=adapter)

    with pytest.raises(SignupDisabledError):
        await service.register_user("new@example.com", "a-long-password", "New", None, None)
    adapter.create_user_with_default_workspace.assert_not_called()


@pytest.mark.asyncio
async def test_a_wrong_code_counts_against_every_active_code(monkeypatch) -> None:
    """Requesting fresh codes must not reset the guess budget of older ones."""
    monkeypatch.setattr(settings, "otp_max_attempts", 5)
    adapter = AsyncMock()
    adapter.get_user_by_email.return_value = AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
    )
    adapter.list_unused_magic_links_for_user.return_value = [
        MagicLinkTokenRecord(
            id=f"ml-{i}",
            user_id="user-1",
            token=f"hash-{i}",
            expires_at=datetime.utcnow().replace(year=2099),
            used=False,
            created_at=datetime.utcnow(),
            otp_code_hash=hash_otp_code(f"11111{i}"),
            otp_attempts=0,
        )
        for i in range(3)
    ]
    adapter.increment_magic_link_otp_attempts.return_value = 1
    service = AuthService(adapter=adapter)

    with pytest.raises(InvalidOtpError):
        await service.verify_otp(
            email="user@example.com", code="000000", user_agent=None, ip_address=None
        )

    charged = {call.args[0] for call in adapter.increment_magic_link_otp_attempts.await_args_list}
    assert charged == {"ml-0", "ml-1", "ml-2"}


def test_a_scoped_token_opens_no_api_route(monkeypatch) -> None:
    """An app-html link token sits in a page URL: it must not act as a session.
    (The links of today are IAM grants; this one is what Nexus used to sign.)"""
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from jose import jwt as jose_jwt
    from naas_abi.apps.nexus.apps.api.app.core.config import current_secret_key
    from naas_abi.apps.nexus.apps.api.app.services.auth import service as auth_service
    from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
        get_auth_service,
        get_current_user_required,
    )

    monkeypatch.setattr(auth_service, "is_access_token_revoked", AsyncMock(return_value=False))
    adapter = AsyncMock()
    adapter.get_user_by_id.return_value = AuthUserRecord(
        id="u-1", email="u@example.com", name="U", hashed_password="x", created_at=datetime.utcnow()
    )
    app = FastAPI()

    @app.get("/api/me")
    async def me(user=Depends(get_current_user_required)) -> dict:
        return {"id": user.id}

    app.dependency_overrides[get_auth_service] = lambda: AuthService(adapter=adapter)
    client = TestClient(app)
    scoped = jose_jwt.encode(
        {
            "sub": "u-1",
            "scope": "app-html",
            "path_prefix": "/app-html/remote/acme/",
            "jti": "j",
            "exp": datetime.utcnow() + timedelta(hours=1),
        },
        current_secret_key(),
        algorithm="HS256",
    )
    session, _ = auth_service.create_access_token({"sub": "u-1"})

    refused = client.get("/api/me", headers={"Authorization": f"Bearer {scoped}"})
    assert refused.status_code == 401
    accepted = client.get("/api/me", headers={"Authorization": f"Bearer {session}"})
    assert accepted.status_code == 200 and accepted.json() == {"id": "u-1"}


def _user(**kwargs) -> AuthUserRecord:
    return AuthUserRecord(
        id="user-1",
        email="user@example.com",
        name="User",
        hashed_password="hashed",
        created_at=datetime.utcnow(),
        **kwargs,
    )


@pytest.mark.asyncio
async def test_a_profile_edit_never_changes_the_email() -> None:
    adapter = AsyncMock()
    adapter.get_user_by_id.return_value = _user()
    adapter.update_user_profile.return_value = _user()
    service = AuthService(adapter=adapter)

    with pytest.raises(EmailChangeNotAllowedError):
        await service.update_profile("user-1", "User", "other@example.com", None, None, None)
    adapter.update_user_profile.assert_not_called()

    # The address it already has is no change; everything else is edited.
    await service.update_profile("user-1", "New", "USER@example.com", "Acme", None, None)
    kwargs = adapter.update_user_profile.await_args.kwargs
    assert kwargs["email"] is None and kwargs["name"] == "New" and kwargs["company"] == "Acme"


@pytest.mark.asyncio
async def test_a_signup_owns_its_personal_workspace_in_iam(nexus_iam) -> None:
    """With the real IAM: the new user is the owner of their own workspace at once
    (not at the next boot), and nobody else reaches it."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ

    nexus_iam.user("stranger")
    adapter = AsyncMock()
    await AuthService(adapter=adapter).open_personal_workspace("new-user")

    assert await AUTHZ.org_of("new-user") == "_none"
    assert await AUTHZ.allowed("DeleteWorkspace", user="new-user", workspace="new-user")
    assert not await AUTHZ.allowed("GetWorkspace", user="stranger", workspace="new-user")
    adapter.place_workspace.assert_awaited_once_with("new-user")
