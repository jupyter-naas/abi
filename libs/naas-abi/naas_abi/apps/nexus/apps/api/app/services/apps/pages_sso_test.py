"""Pages SSO HMAC token mint / verify."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.apps.pages_sso import (
    dev_app_url,
    is_loopback_host,
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


def test_loopback_hosts() -> None:
    for host in (
        "localhost",
        "LOCALHOST",
        "nexus.localhost",
        "127.0.0.1",
        "127.1.2.3",
        "::1",
        "[::1]",
    ):
        assert is_loopback_host(host), host
    for host in (
        "",
        "nexus.example.com",
        "localhost.example.com",
        "10.0.0.1",
        "0.0.0.0",
        "evil-localhost",
    ):
        assert not is_loopback_host(host), host


def test_a_dev_origin_counts_only_on_a_local_nexus_on_loopback() -> None:
    """``nexus_env`` defaults to ``local`` everywhere, so it is not enough alone:
    the Nexus web app must also be on a loopback host, which no deployed one is."""
    urls = "acme.portal:site=http://localhost:9"
    local = {"dev_app_urls": urls, "nexus_env": "local"}
    for frontend in ("http://localhost:3042", "https://nexus.localhost", "http://127.0.0.1:3000"):
        assert (
            dev_app_url("acme.portal:site", frontend_url=frontend, **local) == "http://localhost:9"
        )
    assert dev_app_url("acme.portal:other", frontend_url="http://localhost:3042", **local) is None
    for frontend in ("https://nexus.example.com", "", None):
        assert dev_app_url("acme.portal:site", frontend_url=frontend, **local) is None, frontend
    for env in ("staging", "cloudflare", "", None):
        assert (
            dev_app_url(
                "acme.portal:site",
                dev_app_urls=urls,
                nexus_env=env,
                frontend_url="http://localhost:3042",
            )
            is None
        ), env
    assert (
        dev_app_url(
            "acme.portal:site",
            dev_app_urls="",
            nexus_env="local",
            frontend_url="http://localhost:3042",
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
