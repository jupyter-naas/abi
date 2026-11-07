from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.apps import links
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.preview_token import (
    PreviewGrant,
    mint_preview_token,
    read_preview_token,
)
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    service_account,
    use_call_context,
    user,
)
from naas_abi_core.engine.nats_auth import APP_AUDIENCE, PREVIEW_AUDIENCE
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService


@pytest.fixture(autouse=True)
def iam():
    service = IAMService(IAMStoreMemory())
    service.bootstrap()
    previous = credentials.configure_iam(lambda: service)
    yield service
    credentials.configure_iam(previous)


def _mint(**overrides: object) -> str:
    args = {"user_id": "u-1", "workspace_id": "ws-1", "slug": "demo"}
    args.update(overrides)
    return mint_preview_token(**args)  # type: ignore[arg-type]


def test_round_trip() -> None:
    assert read_preview_token(_mint()) == PreviewGrant("u-1", "ws-1", "demo")


def test_a_preview_link_is_an_iam_grant_that_opens_one_draft_and_nothing_at_the_kernel(
    iam,
) -> None:
    token = _mint()
    record = iam.store.get_key(token.split("_")[2])
    assert (record.kind, record.audience) == ("grant", PREVIEW_AUDIENCE)
    assert record.resource == "preview/ws-1/demo"
    assert record.scope == ()  # allows nothing at the kernel
    assert record.expires_at is not None


def test_a_preview_token_is_never_a_session_token_nor_an_api_credential() -> None:
    """The previewed app can read its URL; the token must not open the API."""
    import asyncio

    token = _mint()
    assert asyncio.run(credentials.bearer_credential(token)) is None
    assert credentials.accepted_kinds("/api/workspaces") == {"session", "api-key"}


def test_a_token_signed_with_the_old_secret_is_not_a_preview_token() -> None:
    from jose import jwt

    old = jwt.encode(
        {"sub": "u-1", "scope": "app-preview", "uid": "u-1", "ws": "ws-1", "slug": "demo"},
        "the-key-nexus-used-to-sign-with",
        algorithm="HS256",
    )
    assert read_preview_token(old) is None


def test_another_kind_of_link_is_not_a_preview_token() -> None:
    app_link, _ = links.mint_link(
        user_id="u-1", audience=APP_AUDIENCE, resource="/app-html/", minutes=5
    )
    assert read_preview_token(app_link) is None


def test_tampered_unknown_revoked_and_suspended_links_are_refused(iam) -> None:
    token = _mint()
    assert read_preview_token(token[:-2] + "xx") is None
    assert read_preview_token("abi_gk_aaaaaaaaaaaaaaaa_nope") is None
    assert read_preview_token("not-a-token") is None
    assert read_preview_token("") is None
    with use_call_context(CallContext(principal=service_account("api"), on_behalf_of=user("u-1"))):
        iam.revoke_key("u-1", token.split("_")[2])
    assert read_preview_token(token) is None

    other = _mint(user_id="u-2")
    assert read_preview_token(other) is not None
    with as_service_account("engine"):
        iam.suspend_principal(iam.resolve_user("u-2").id)
    assert read_preview_token(other) is None


def test_a_preview_link_lasts_eight_hours_at_most(iam) -> None:
    token = _mint(minutes=24 * 60)
    record = iam.store.get_key(token.split("_")[2])
    from datetime import UTC, datetime, timedelta

    assert record.expires_at <= datetime.now(UTC) + timedelta(hours=8, seconds=2)
