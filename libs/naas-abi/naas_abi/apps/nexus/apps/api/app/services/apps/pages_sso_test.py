"""Pages SSO HMAC token mint / verify."""

from __future__ import annotations

import base64
import json
import logging

import pytest
from naas_abi.apps.nexus.apps.api.app.services.apps.pages_sso import (
    dev_app_url,
    is_loopback_host,
    mint_pages_sso_token,
    pages_sso_audiences,
    parse_dev_app_urls,
    portal_secrets,
    read_portal_secrets,
    shared_secret_warning,
    verify_pages_sso_token,
)

APP = "acme.portal:site"
OTHER = "acme.portal:other"


def _claims(token: str) -> dict:
    body = token.split(".")[0]
    return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))


def test_mint_roundtrip() -> None:
    token, lifetime = mint_pages_sso_token(
        email="Alex.Rivera@example.com",
        audience="portal.example.com",
        app_id=APP,
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
        app_id=APP,
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
        app_id=APP,
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
            app_id=APP,
            secret="test-secret",
        )
    except ValueError as exc:
        assert "hostname" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_a_token_names_its_app_and_a_portal_may_check_it_or_not() -> None:
    """``app`` is the app id. A portal that checks only ``aud``, ``scope``,
    ``exp`` and ``email`` (no ``app_id``) still accepts the token; one that
    names the app accepts it for that app alone."""
    token, _ = mint_pages_sso_token(
        email="alex@example.com", audience="portal.example.com", app_id=APP, secret="s"
    )
    claims = _claims(token)
    assert claims["app"] == APP
    assert set(claims) == {"app", "aud", "email", "exp", "scope"}
    check = {"secret": "s", "audience": "portal.example.com"}
    assert verify_pages_sso_token(token, **check) == "alex@example.com"
    assert verify_pages_sso_token(token, app_id=APP, **check) == "alex@example.com"
    assert verify_pages_sso_token(token, app_id=OTHER, **check) is None
    assert verify_pages_sso_token(token, app_id="", **check) is None


def test_a_token_is_for_one_app_even_on_a_shared_host() -> None:
    """Two apps on ``localhost`` (one through the dev map), each with its own
    secret: A's token does not verify with B's secret, and with A's secret it
    is refused for B."""
    secrets = {APP: "secret-a", OTHER: "secret-b"}
    token, _ = mint_pages_sso_token(
        email="alex@example.com", audience="localhost", app_id=APP, secret=secrets[APP]
    )
    assert verify_pages_sso_token(token, secret=secrets[OTHER], audience="localhost") is None
    assert (
        verify_pages_sso_token(token, secret=secrets[APP], audience="localhost", app_id=APP)
        == "alex@example.com"
    )
    assert (
        verify_pages_sso_token(token, secret=secrets[APP], audience="localhost", app_id=OTHER)
        is None
    )


@pytest.mark.parametrize("app_id", ["", "  "])
def test_a_token_without_an_app_is_not_minted(app_id: str) -> None:
    with pytest.raises(ValueError, match="names its app"):
        mint_pages_sso_token(
            email="a@b.com", audience="portal.example.com", app_id=app_id, secret="s"
        )


def test_a_token_without_a_secret_is_not_minted() -> None:
    with pytest.raises(ValueError):
        mint_pages_sso_token(email="a@b.com", audience="portal.example.com", app_id=APP, secret="")


def test_portal_secrets_drop_empty_entries() -> None:
    assert portal_secrets(None) == {}
    assert portal_secrets({APP: " s ", OTHER: "", " ": "x", "acme.x:y": "  "}) == {APP: "s"}


def test_the_shared_secret_left_in_the_environment_is_said_at_start() -> None:
    assert shared_secret_warning({}) is None
    assert shared_secret_warning({"PAGES_SSO_SECRET": " "}) is None
    message = shared_secret_warning({"PAGES_SSO_SECRET": "zq-old-shared-value"})
    assert message is not None
    assert "signs nothing" in message
    assert "pages_sso_secrets" in message and "PAGES_SSO_SECRETS" in message
    assert "zq-old-shared-value" not in message


def test_the_shared_secret_is_found_whatever_the_case_of_its_name() -> None:
    """``Settings`` read names without case, so a lowercase ``.env`` entry counted."""
    assert shared_secret_warning({"pages_sso_secret": "old"}) is not None


def test_portal_secrets_are_read_from_a_map_or_its_json() -> None:
    assert read_portal_secrets(None) == {}
    assert read_portal_secrets("") == {}
    assert read_portal_secrets("  ") == {}
    assert read_portal_secrets({APP: "s", OTHER: ""}) == {APP: "s"}
    assert read_portal_secrets(f'{{"{APP}": " s "}}') == {APP: "s"}
    assert read_portal_secrets(f'{{"{APP}": "s"}}'.encode()) == {APP: "s"}


@pytest.mark.parametrize(
    "raw", ["zq-secret", "[1]", '"zq-secret"', '{"a:b": 1}', {"a:b": 1}, 42, "{not json"]
)
def test_a_malformed_portal_secrets_value_is_none_and_logged_without_it(
    raw: object, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        assert read_portal_secrets(raw) == {}
    said = " ".join(r.getMessage() for r in caplog.records)
    assert '{"<module_path>:<app_dir>": "<secret>"}' in said
    assert "zq-secret" not in said
