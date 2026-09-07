"""Tests for short-lived /app-html JWT access."""

from __future__ import annotations

from datetime import timedelta

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.apps import app_html_access
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    create_access_token,
    decode_token,
)
from starlette.requests import Request


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
        }
    )


def test_validate_accepts_user_session_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "secret_key", "test-secret-key")
    token, _ = create_access_token(
        data={"sub": "user-1"},
        expires_delta=timedelta(minutes=15),
    )
    assert app_html_access.validate_app_html_jwt(token, _request("/app-html/axi/devops/host/"))


def test_validate_rejects_expired_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "secret_key", "test-secret-key")
    token, _ = create_access_token(
        data={"sub": "user-1"},
        expires_delta=timedelta(minutes=-1),
    )
    assert decode_token(token) is None
    assert (
        app_html_access.validate_app_html_jwt(token, _request("/app-html/axi/devops/host/"))
        is False
    )


def test_validate_scoped_path_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "secret_key", "test-secret-key")
    token, expires_in = app_html_access.mint_app_html_access_token(
        user_id="user-1",
        expires_minutes=10,
        path_prefix="/app-html/axi/devops/",
    )
    assert expires_in == 600
    assert app_html_access.validate_app_html_jwt(
        token, _request("/app-html/axi/devops/host/")
    )
    assert (
        app_html_access.validate_app_html_jwt(
            token, _request("/app-html/osint/osint/")
        )
        is False
    )


def test_mint_rejects_invalid_path_prefix() -> None:
    with pytest.raises(ValueError, match="path_prefix"):
        app_html_access.mint_app_html_access_token(
            user_id="user-1",
            path_prefix="/not-app-html/",
        )
