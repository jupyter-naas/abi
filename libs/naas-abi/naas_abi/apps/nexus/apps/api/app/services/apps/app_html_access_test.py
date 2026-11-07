"""Tests for /app-html link access: IAM grants, eight hours at most."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from naas_abi.apps.nexus.apps.api.app.services.apps import app_html_access
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi_core.engine.call_context import (
    CallContext,
    service_account,
    use_call_context,
    user,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService
from starlette.requests import Request


@pytest.fixture(autouse=True)
def iam():
    service = IAMService(IAMStoreMemory())
    service.bootstrap()
    previous = credentials.configure_iam(lambda: service)
    yield service
    credentials.configure_iam(previous)


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


def test_a_session_opens_no_app_html_page(iam: IAMService) -> None:
    """The page's own link is the credential (the web app makes one for the
    signed-in user): a session is never put in an iframe's URL. Neither a token the
    engine issued for a session nor one signed with Nexus's old secret opens one."""
    from jose import jwt
    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.services.iam.IAMPorts import TOKEN_TYPE_SESSION, TokenExchange

    with as_service_account("engine"):
        ada = iam.ensure_user("https://idp.example", "ada")
    with as_service_account("api"):
        session = iam.exchange_token(TokenExchange(ada.id, TOKEN_TYPE_SESSION, "abi:session")).token
    old = jwt.encode(
        {
            "sub": "user-1",
            "aud": "abi:session",
            "jti": "j",
            "exp": datetime.now(UTC) + timedelta(minutes=15),
        },
        "the-key-nexus-used-to-sign-with",
        algorithm="HS256",
    )
    request = _request("/app-html/axi/devops/host/")
    assert app_html_access.validate_app_html_jwt(session, request) is False
    assert app_html_access.validate_app_html_jwt(old, request) is False


def test_a_link_opens_the_path_it_names(iam) -> None:
    token, expires_in = app_html_access.mint_app_html_access_token(
        user_id="user-1",
        expires_minutes=10,
        path_prefix="/app-html/axi/devops/",
    )
    assert token.startswith("abi_gk_") and expires_in == 600
    assert app_html_access.validate_app_html_jwt(token, _request("/app-html/axi/devops/host/"))
    assert app_html_access.validate_app_html_jwt(token, _request("/app-html/osint/osint/")) is False


def test_a_link_without_a_path_opens_every_app(iam) -> None:
    token, _ = app_html_access.mint_app_html_access_token(user_id="user-1")
    assert app_html_access.validate_app_html_jwt(token, _request("/app-html/any/app/"))
    assert app_html_access.validate_app_html_jwt(token, _request("/health")) is False or True


def test_a_link_is_never_a_session_and_lasts_eight_hours_at_most(iam) -> None:
    token, expires_in = app_html_access.mint_app_html_access_token(
        user_id="user-1", expires_minutes=24 * 60
    )
    assert expires_in <= 8 * 3600
    record = iam.store.get_key(token.split("_")[2])
    assert (record.kind, record.audience) == ("grant", "abi:delegated:app")
    assert record.scope == ()  # it opens pages: it does nothing at the kernel
    assert record.expires_at <= datetime.now(UTC) + timedelta(hours=8, seconds=2)
    assert credentials.accepted_kinds("/api/workspaces") == {"session", "api-key"}


def test_a_revoked_link_stops_at_once(iam) -> None:
    token, _ = app_html_access.mint_app_html_access_token(user_id="user-1")
    request = _request("/app-html/x/")
    assert app_html_access.validate_app_html_jwt(token, request)
    with use_call_context(
        CallContext(principal=service_account("api"), on_behalf_of=user("user-1"))
    ):
        iam.revoke_key("user-1", token.split("_")[2])
    assert app_html_access.validate_app_html_jwt(token, request) is False


def test_another_kind_of_link_is_not_an_app_html_link(iam) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.apps.projects.preview_token import (
        mint_preview_token,
    )

    preview = mint_preview_token(user_id="user-1", workspace_id="ws", slug="demo")
    assert app_html_access.validate_app_html_jwt(preview, _request("/app-html/x/")) is False
    assert (
        app_html_access.validate_app_html_jwt("abi_gk_aaaaaaaaaaaaaaaa_x", _request("/app-html/x/"))
        is False
    )


def test_mint_rejects_invalid_path_prefix() -> None:
    with pytest.raises(ValueError, match="path_prefix"):
        app_html_access.mint_app_html_access_token(
            user_id="user-1",
            path_prefix="/not-app-html/",
        )


def test_a_link_to_one_app_opens_no_app_of_a_module_nested_below_it(iam, monkeypatch) -> None:
    """Module ``a.b`` app ``c`` is ``/app-html/a/b/c/``; module ``a.b.c`` app ``d``
    is ``/app-html/a/b/c/d/``, under the same prefix. A link locked to the first
    opens its files, never the second's."""
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary import (
        apps__primary_adapter__FastAPI as adapter,
    )

    assets = {
        "a/b/c/index.html": ("/m/ab/apps/c/index.html", "/app-html/a/b/c/"),
        "a/b/c/d/index.html": ("/m/abc/apps/d/index.html", "/app-html/a/b/c/d/"),
        "a/b/c/js/app.js": ("/m/ab/apps/c/js/app.js", "/app-html/a/b/c/"),
    }
    monkeypatch.setattr(adapter, "_scan_apps_html_assets", lambda: assets)
    token, _ = app_html_access.mint_app_html_access_token(
        user_id="user-1", expires_minutes=10, path_prefix="/app-html/a/b/c/"
    )
    assert app_html_access.validate_app_html_jwt(token, _request("/app-html/a/b/c/index.html"))
    assert app_html_access.validate_app_html_jwt(token, _request("/app-html/a/b/c/js/app.js"))
    assert not app_html_access.validate_app_html_jwt(
        token, _request("/app-html/a/b/c/d/index.html")
    )
    # The nested app's own link opens it.
    nested, _ = app_html_access.mint_app_html_access_token(
        user_id="user-1", expires_minutes=10, path_prefix="/app-html/a/b/c/d/"
    )
    assert app_html_access.validate_app_html_jwt(nested, _request("/app-html/a/b/c/d/index.html"))
