from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.core.config import Settings
from naas_abi.apps.nexus.apps.api.app.services.apps import links
from naas_abi_core.engine.nats_auth import APP_AUDIENCE
from naas_abi_core.services.iam.IAMPorts import KeyRecord


@pytest.fixture(autouse=True)
def _engine(engine_iam):
    return engine_iam


@pytest.fixture
def ada(engine_iam):
    from naas_abi_core.engine.call_context import as_service_account

    with as_service_account("engine"):
        return engine_iam.ensure_user("https://idp.example", "ada")


def test_a_longer_lifetime_than_eight_hours_boots_and_the_link_is_clamped(ada):
    """A deployment that set a day (valid before links were grants) still boots;
    the link it makes lasts eight hours."""
    settings = Settings(
        app_html_access_token_expire_minutes=24 * 60,
        app_preview_token_expire_minutes=24 * 60,
        remote_app_grant_expire_minutes=24 * 60,
    )
    _, seconds = links.mint_link(
        user_id=ada.id,
        audience=APP_AUDIENCE,
        resource=links.APP_HTML_ROOT,
        minutes=settings.app_html_access_token_expire_minutes,
    )
    assert seconds == 8 * 60 * 60


def test_the_limit_of_open_links_is_a_refusal_with_its_own_name(ada, engine_iam):
    now = datetime.now(UTC)
    for index in range(1000):
        engine_iam.store.create_key(
            KeyRecord(
                key_id=f"link-{index:011d}",
                principal_id=ada.id,
                secret_hash="x",
                kind="grant",
                audience=APP_AUDIENCE,
                created_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
    with pytest.raises(links.LinkLimitReached):
        links.mint_link(
            user_id=ada.id,
            audience=APP_AUDIENCE,
            resource=links.APP_HTML_ROOT,
            minutes=5,
        )


def test_a_link_route_answers_429_at_the_limit_not_500(nexus_iam, monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary import (
        apps__primary_adapter__FastAPI as routes,
    )

    def full(**_):
        raise links.LinkLimitReached("Too many links are open for this account")

    # The caller may use apps in the workspace the request names: only the
    # link is refused, and with a 429.
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope

    workspace = nexus_iam.workspace("org-1", "ws-1")
    nexus_iam.grant("ada", "owner", workspace)
    nexus_iam.allow_scope("ada", ModuleScope("app", "acme.ops", "map"), workspace)
    monkeypatch.setattr(routes, "mint_app_html_access_token", full)
    monkeypatch.setattr(routes, "_app_id_of_prefix", lambda prefix: "acme.ops:map")
    user = type("User", (), {"id": "ada"})()
    with pytest.raises(HTTPException) as caught:
        asyncio.run(
            routes.create_app_html_access_token(
                routes.AppHtmlAccessTokenRequest(
                    workspace_id="ws-1", path_prefix="/app-html/acme/ops/map/"
                ),
                current_user=user,
            )
        )
    assert caught.value.status_code == 429


def test_a_key_narrowed_to_reading_cannot_make_a_link(ada, engine_iam):
    """A link is the user's own credential for an app: a request that came with
    a narrower one must not widen into it."""
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
        user,
    )
    from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError

    read_only = ({"effect": "Allow", "actions": ["triple_store:Query"], "resources": ["*"]},)
    request = CallContext(
        principal=service_account("api"), on_behalf_of=user(ada.id), scope=read_only
    )
    with use_call_context(request), pytest.raises(PermissionDeniedError, match="limit"):
        links.mint_link(
            user_id=ada.id, audience=APP_AUDIENCE, resource=links.APP_HTML_ROOT, minutes=5
        )
    assert engine_iam.store.list_keys(ada.id) == []
    # Without a narrower credential (a session) it is made, as before.
    value, _ = links.mint_link(
        user_id=ada.id, audience=APP_AUDIENCE, resource=links.APP_HTML_ROOT, minutes=5
    )
    assert value.startswith("abi_gk_")


def test_an_iam_refusal_is_a_403_not_a_server_error():
    from naas_abi.apps.nexus.apps.api.app.services.exceptions import (
        _resolve_exception_mapping,
    )
    from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError

    status, _ = _resolve_exception_mapping(PermissionDeniedError("iam:CreateKey", "k"))
    assert status == 403
