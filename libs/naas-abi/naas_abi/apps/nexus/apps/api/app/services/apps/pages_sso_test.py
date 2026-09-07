"""Pages SSO HMAC token mint / verify."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.apps.pages_sso import (
    mint_pages_sso_token,
    verify_pages_sso_token,
)


def test_mint_roundtrip() -> None:
    token, lifetime = mint_pages_sso_token(
        email="Alex.Rivera@example.com",
        audience="portal.example.com",
        secret="test-secret",
        expires_seconds=120,
    )
    assert lifetime == 120
    assert (
        verify_pages_sso_token(
            token,
            secret="test-secret",
            audience="portal.example.com",
        )
        == "alex.rivera@example.com"
    )


def test_wrong_audience_rejected() -> None:
    token, _ = mint_pages_sso_token(
        email="alex.rivera@example.com",
        audience="portal.example.com",
        secret="test-secret",
    )
    assert (
        verify_pages_sso_token(
            token,
            secret="test-secret",
            audience="other.example.com",
        )
        is None
    )


def test_wrong_secret_rejected() -> None:
    token, _ = mint_pages_sso_token(
        email="alex.rivera@example.com",
        audience="portal.example.com",
        secret="test-secret",
    )
    assert (
        verify_pages_sso_token(
            token,
            secret="other",
            audience="portal.example.com",
        )
        is None
    )


def test_mint_rejects_url_audience() -> None:
    try:
        mint_pages_sso_token(
            email="a@b.com",
            audience="https://portal.example.com",
            secret="test-secret",
        )
    except ValueError as exc:
        assert "hostname" in str(exc)
    else:
        raise AssertionError("expected ValueError")
