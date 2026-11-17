"""The web app's pass: it names its live user to the web app's server routes, and opens nothing."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, Request
from naas_abi.apps.nexus.apps.api.app.services.apps import app_html_access, links
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.grant import read_remote_app_grant
from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.primary.oidc__primary_adapter__FastAPI import (  # noqa: E501
    router as oidc_router,
)
from naas_abi.apps.nexus.apps.api.app.services.oidc.web_pass import (
    WEB_PASS_HEADER,
    mint_web_pass,
    read_web_pass,
)
from naas_abi_core.engine.nats_auth import APP_AUDIENCE
from starlette.requests import Request as StarletteRequest


@pytest.fixture
def ada(engine_iam):
    from naas_abi_core.engine.call_context import as_service_account

    with as_service_account("engine"):
        return engine_iam.ensure_user("https://idp.example", "ada")


def _app(session_user: str | None, *, session_ends: datetime | None = None) -> FastAPI:
    """The sign-in routes, with the session the identity middleware would leave."""
    app = FastAPI()

    @app.middleware("http")
    async def _session(request: Request, call_next):
        request.state.nexus_session = (
            SimpleNamespace(user_id=session_user, expires_at=session_ends) if session_user else None
        )
        request.state.nexus_csrf_failed = False
        return await call_next(request)

    app.include_router(oidc_router, prefix="/api/auth/oidc")
    return app


async def _call(app: FastAPI, method: str, headers: dict[str, str] | None = None):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://api.test"
    ) as client:
        return await client.request(method, "/api/auth/oidc/web-pass", headers=headers or {})


def test_web_pass_keeps_naming_only_its_live_user(ada):
    value, seconds = asyncio.run(mint_web_pass(ada.id))
    assert 0 < seconds <= links.MAX_MINUTES * 60
    found = asyncio.run(read_web_pass(value))
    assert found is not None and found[0] == ada.id

    assert asyncio.run(read_web_pass(None)) is None
    assert asyncio.run(read_web_pass("")) is None
    assert asyncio.run(read_web_pass(value + "x")) is None

    # Sign-out ends every pass of the user.
    assert links.revoke_web_passes(ada.id) == 1
    assert asyncio.run(read_web_pass(value)) is None


def test_web_pass_keeps_apart_from_app_links(ada):
    """An app link is no pass, and a pass opens no app."""
    app_link, _ = links.mint_link(
        user_id=ada.id, audience=APP_AUDIENCE, resource=links.APP_HTML_ROOT, minutes=5
    )
    assert asyncio.run(read_web_pass(app_link)) is None

    value, _ = asyncio.run(mint_web_pass(ada.id))
    page = StarletteRequest(
        {"type": "http", "method": "GET", "path": "/app-html/x/index.html", "headers": []}
    )
    assert app_html_access.validate_app_html_jwt(value, page) is False
    assert read_remote_app_grant(value) is None

    # Ending remote app grants leaves the pass, and ending passes leaves the app link.
    assert links.revoke_remote_app_links(ada.id) == 0
    assert links.revoke_web_passes(ada.id) == 1
    assert links.open_link(app_link, APP_AUDIENCE) is not None


def test_web_pass_route_keeps_passes_for_signed_in_sessions_only(ada):
    refused = asyncio.run(_call(_app(None), "POST"))
    assert refused.status_code == 401

    made = asyncio.run(_call(_app(ada.id), "POST"))
    assert made.status_code == 200, made.text
    value = made.json()["web_pass"]
    assert made.json()["expires_in"] > 0

    anonymous = _app(None)
    assert asyncio.run(_call(anonymous, "GET")).status_code == 401
    assert asyncio.run(_call(anonymous, "GET", {WEB_PASS_HEADER: "abi_gk_x_y"})).status_code == 401
    checked = asyncio.run(_call(anonymous, "GET", {WEB_PASS_HEADER: value}))
    assert checked.status_code == 200, checked.text
    assert checked.json()["user_id"] == ada.id


def test_web_pass_keeps_within_its_session(ada):
    """A pass never outlives the session it was made from."""
    soon = datetime.now(UTC) + timedelta(minutes=10)
    _, seconds = asyncio.run(mint_web_pass(ada.id, not_after=soon))
    assert 0 < seconds <= 10 * 60

    # The session's end, naive UTC as the session record keeps it.
    ends = (datetime.now(UTC) + timedelta(minutes=5)).replace(tzinfo=None)
    made = asyncio.run(_call(_app(ada.id, session_ends=ends), "POST"))
    assert made.status_code == 200, made.text
    assert 0 < made.json()["expires_in"] <= 5 * 60
    found = asyncio.run(read_web_pass(made.json()["web_pass"]))
    assert found is not None and 0 < found[1] <= 5 * 60

    ended = (datetime.now(UTC) - timedelta(minutes=1)).replace(tzinfo=None)
    assert asyncio.run(_call(_app(ada.id, session_ends=ended), "POST")).status_code == 401
