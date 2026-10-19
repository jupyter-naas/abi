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


def test_a_link_route_answers_429_at_the_limit_not_500(ada, monkeypatch):
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary import (
        apps__primary_adapter__FastAPI as routes,
    )

    def full(**_):
        raise links.LinkLimitReached("Too many links are open for this account")

    monkeypatch.setattr(routes, "mint_app_html_access_token", full)
    user = type("User", (), {"id": ada.id})()
    with pytest.raises(HTTPException) as caught:
        asyncio.run(
            routes.create_app_html_access_token(
                routes.AppHtmlAccessTokenRequest(), current_user=user
            )
        )
    assert caught.value.status_code == 429
