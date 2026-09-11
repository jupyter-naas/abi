from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jose import jwt
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.preview_token import (
    PreviewGrant,
    _key,
    mint_preview_token,
    read_preview_token,
)
from naas_abi.apps.nexus.apps.api.app.services.auth import service as auth_service

SECRET = "s3cret-for-tests"


def _mint(**overrides: object) -> str:
    args = {"secret": SECRET, "user_id": "u-1", "workspace_id": "ws-1", "slug": "demo"}
    args.update(overrides)
    return mint_preview_token(**args)  # type: ignore[arg-type]


def test_round_trip() -> None:
    assert read_preview_token(_mint(), secret=SECRET) == PreviewGrant("u-1", "ws-1", "demo")


def test_a_preview_token_is_never_a_session_token(monkeypatch) -> None:
    """The previewed app can read its URL; the token must not open the API."""
    monkeypatch.setattr(auth_service.settings, "secret_key", SECRET)
    assert auth_service.decode_token(_mint()) is None


def test_a_session_token_is_not_a_preview_token(monkeypatch) -> None:
    monkeypatch.setattr(auth_service.settings, "secret_key", SECRET)
    session, _ = auth_service.create_access_token(
        {"sub": "u-1", "scope": "app-preview", "uid": "u-1", "ws": "ws-1", "slug": "demo"}
    )
    assert read_preview_token(session, secret=SECRET) is None


def test_tampered_other_secret_and_expired_tokens_are_refused() -> None:
    token = _mint()
    assert read_preview_token(token[:-2] + "xx", secret=SECRET) is None
    assert read_preview_token(token, secret="other") is None
    assert read_preview_token("not-a-jwt", secret=SECRET) is None
    expired = jwt.encode(
        {
            "scope": "app-preview",
            "uid": "u-1",
            "ws": "ws-1",
            "slug": "demo",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        _key(SECRET),
        algorithm="HS256",
    )
    assert read_preview_token(expired, secret=SECRET) is None
