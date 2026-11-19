"""Pages SSO HMAC token mint / verify."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.apps.pages_sso import (
    mint_pages_sso_token,
    pages_sso_audiences,
    parse_dev_app_urls,
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


def test_audiences_are_the_portal_hosts() -> None:
    assert pages_sso_audiences("https://portal.example.com/login") == frozenset(
        {"portal.example.com"}
    )
    assert pages_sso_audiences("https://portal.example.com", "http://localhost:9") == frozenset(
        {"portal.example.com", "localhost"}
    )
    assert pages_sso_audiences(None, "") == frozenset()


def test_dev_app_urls_have_no_built_in_entry() -> None:
    assert parse_dev_app_urls(None) == {}
    assert parse_dev_app_urls("") == {}
    assert parse_dev_app_urls(
        "acme.portal:site=http://localhost:9, other.app=http://127.0.0.1:8080"
    ) == {
        "acme.portal:site": "http://localhost:9",
        "other.app": "http://127.0.0.1:8080",
    }


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
