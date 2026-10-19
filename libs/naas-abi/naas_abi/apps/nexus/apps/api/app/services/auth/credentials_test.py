"""Credentials: which kinds the Nexus API reads, and where (RFC §9.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi.apps.nexus.apps.api.app.services.auth.credentials import (
    API_KEY,
    CODING,
    SESSION,
    accepted_kinds,
    bearer_credential,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    create_access_token,
    decode_token,
    is_session_token,
)
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    service_account,
    use_call_context,
    user,
)
from naas_abi_core.engine.nats_auth import (
    AGENT_AUDIENCE,
    API_KEY_AUDIENCE,
    APP_AUDIENCE,
    CODING_AUDIENCE,
    PREVIEW_AUDIENCE,
    SESSION_AUDIENCE,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMPorts import (
    TOKEN_TYPE_JWT,
    TOKEN_TYPE_SESSION,
    TokenExchange,
)
from naas_abi_core.services.iam.IAMService import IAMService


@pytest.fixture
def iam(monkeypatch):
    service = IAMService(IAMStoreMemory())
    service.bootstrap()
    previous = credentials.configure_iam(lambda: service)
    yield service
    credentials.configure_iam(previous)


@pytest.fixture
def ada(iam):
    with as_service_account("engine"):
        return iam.ensure_user("https://idp.example", "ada")


def _acting_for(record):
    return use_call_context(
        CallContext(principal=service_account("api"), on_behalf_of=user(record.id))
    )


def _vouched(iam, record, audience, **fields):
    with as_service_account("api"):
        return iam.exchange_token(
            TokenExchange(
                subject_token=record.id,
                subject_token_type=TOKEN_TYPE_SESSION,
                audience=audience,
                **fields,
            )
        ).token


async def _never_revoked(jti: str) -> bool:
    return False


def credential(token):
    import asyncio

    # The revocation list of access tokens is Nexus's database: none here.
    return asyncio.run(bearer_credential(token, is_revoked=_never_revoked))


# -- which route takes which kind ---------------------------------------------------------------


def test_the_routes_take_the_kinds_they_were_made_for():
    assert accepted_kinds("/api/workspaces") == {SESSION, API_KEY}
    assert accepted_kinds("/api/chat/stream") == {SESSION, API_KEY}
    # A coding agent's credential reaches the OpenAI gateway and nothing else.
    assert accepted_kinds("/api/v1/chat/completions") == {SESSION, API_KEY, CODING}
    # The account and the credentials' own administration take no key.
    assert accepted_kinds("/api/auth/me") == {SESSION}
    assert accepted_kinds("/api/auth/logout") == {SESSION}
    assert accepted_kinds("/api/iam/api-keys") == {SESSION}
    # Anything that is not the API (the WebSocket, an app) takes a session only.
    assert accepted_kinds("/socket.io/") == {SESSION}
    assert accepted_kinds("/app-html/x") == {SESSION}
    assert accepted_kinds("/health") == {SESSION}


# -- the session Nexus signs --------------------------------------------------------------------


def test_a_session_token_is_a_session_and_names_its_user():
    token, jti = create_access_token({"sub": "usr-1"})
    payload = decode_token(token)
    assert payload is not None and payload["aud"] == SESSION_AUDIENCE
    assert is_session_token(payload)
    found = credential(token)
    assert found is not None and (found.kind, found.user_id) == (SESSION, "usr-1")
    assert found.token_id == jti


def test_a_token_made_before_sessions_had_an_audience_is_no_session():
    from jose import jwt
    from naas_abi.apps.nexus.apps.api.app.core.config import current_secret_key

    old = jwt.encode(
        {"sub": "usr-1", "jti": "j", "exp": datetime.now(UTC) + timedelta(hours=1)},
        current_secret_key(),
        algorithm="HS256",
    )
    assert decode_token(old) is None
    assert credential(old) is None


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "usr-1", "scope": "app-html"},  # an app-html link
        {"sub": "usr-1", "scope": "app-html", "path_prefix": "/app-html/x/"},
        {"sub": "usr-1", "aud": "abi:delegated:coding"},
    ],
)
def test_a_link_or_another_audience_signed_with_the_secret_is_no_session(claims):
    from jose import jwt
    from naas_abi.apps.nexus.apps.api.app.core.config import current_secret_key

    token = jwt.encode(
        {**claims, "jti": "j", "exp": datetime.now(UTC) + timedelta(hours=1)},
        current_secret_key(),
        algorithm="HS256",
    )
    assert credential(token) is None


def test_create_access_token_never_signs_another_audience():
    token, _ = create_access_token({"sub": "usr-1", "aud": "abi:delegated:coding"})
    assert decode_token(token)["aud"] == SESSION_AUDIENCE


def test_a_session_token_revoked_by_its_users_floor_is_no_session(iam, ada):
    token, _ = create_access_token({"sub": ada.id})
    assert credential(token) is not None
    with _acting_for(ada):
        iam.revoke_tokens(ada.id)
    assert credential(token) is None


def test_a_suspended_user_has_no_session(iam, ada):
    token, _ = create_access_token({"sub": ada.id})
    with as_service_account("engine"):
        iam.suspend_principal(ada.id)
    assert credential(token) is None


def test_a_nexus_user_iam_never_heard_of_keeps_a_session(iam):
    token, _ = create_access_token({"sub": "9f2d5c0e-0000-4000-8000-000000000001"})
    found = credential(token)
    assert found is not None and found.kind == SESSION


# -- engine tokens ------------------------------------------------------------------------------


def test_an_engine_session_token_is_a_session(iam, ada):
    found = credential(_vouched(iam, ada, SESSION_AUDIENCE))
    assert found is not None and (found.kind, found.user_id) == (SESSION, ada.id)


def test_an_api_key_and_a_coding_token_are_their_own_kinds(iam, ada):
    session = _vouched(iam, ada, SESSION_AUDIENCE)
    with as_service_account("api"):
        api_key = iam.exchange_token(TokenExchange(session, TOKEN_TYPE_JWT, API_KEY_AUDIENCE)).token
        coding = iam.exchange_token(TokenExchange(session, TOKEN_TYPE_JWT, CODING_AUDIENCE)).token
    assert credential(api_key).kind == API_KEY
    assert credential(coding).kind == CODING


@pytest.mark.parametrize("audience", [APP_AUDIENCE, PREVIEW_AUDIENCE])
def test_an_app_or_preview_token_is_no_credential_of_the_api(iam, ada, audience):
    session = _vouched(iam, ada, SESSION_AUDIENCE)
    with as_service_account("api"):
        narrow = iam.exchange_token(TokenExchange(session, TOKEN_TYPE_JWT, audience))
    assert credential(narrow.token) is None


def test_an_agent_delegation_is_no_credential_of_the_api(iam, ada):
    # It names the module acting for the user: the kernel's, never a session.
    assert credential(_vouched(iam, ada, AGENT_AUDIENCE)) is None


def test_a_service_account_token_is_no_credential_of_the_api(iam):
    assert credential(iam.issue_service_token("api").token) is None
    assert credential(iam.issue_service_token("engine").token) is None


def test_a_scope_travels_with_the_credential(iam, ada):
    scope = ({"effect": "Allow", "actions": ["triple_store:Query"], "resources": ["*"]},)
    found = credential(_vouched(iam, ada, SESSION_AUDIENCE, scope=scope))
    assert found is not None and found.scope == scope


def test_tokens_revoked_or_of_a_suspended_user_are_refused(iam, ada):
    token = _vouched(iam, ada, SESSION_AUDIENCE)
    assert credential(token) is not None
    with as_service_account("engine"):
        iam.suspend_principal(ada.id)
    assert credential(token) is None
    with as_service_account("engine"):
        iam.resume_principal(ada.id)
    assert credential(token) is not None
    with _acting_for(ada):
        iam.revoke_tokens(ada.id)
    assert credential(token) is None


def test_engine_tokens_are_refused_without_an_engine_iam():
    previous = credentials.configure_iam(lambda: None)
    try:
        assert credential("a.b.c") is None
        assert credential("abi_pk_aaaaaaaaaaaaaaaa_secret") is None
    finally:
        credentials.configure_iam(previous)


def test_a_forged_or_foreign_token_is_refused(iam, ada):
    from naas_abi_core.engine.nats_test_tokens import OTHER_TOKENS

    forged = OTHER_TOKENS.token(ada.id, kind="user", audience=SESSION_AUDIENCE)
    assert credential(forged) is None
    assert credential("not a token") is None
    assert credential("") is None


# -- personal keys ------------------------------------------------------------------------------


def _key(iam, record, **fields):
    with _acting_for(record):
        return iam.create_key(record.id, **fields)


def test_a_personal_key_presented_as_the_bearer_is_an_api_key_credential(iam, ada):
    scope = ({"effect": "Allow", "actions": ["triple_store:Query"], "resources": ["*"]},)
    created = _key(iam, ada, scope=scope)
    found = credential(created.value)
    assert found is not None
    assert (found.kind, found.user_id, found.scope) == (API_KEY, ada.id, scope)


def test_a_coding_key_is_a_coding_credential_bound_to_its_environment(iam, ada):
    created = _key(
        iam,
        ada,
        audience=CODING_AUDIENCE,
        resource="http://coder-ada-x:8378",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    found = credential(created.value)
    assert found is not None
    assert (found.kind, found.resource) == (CODING, "http://coder-ada-x:8378")


def test_a_revoked_key_is_no_credential_on_the_next_request(iam, ada):
    created = _key(iam, ada)
    assert credential(created.value) is not None
    with _acting_for(ada):
        iam.revoke_key(ada.id, created.record.key_id)
    assert credential(created.value) is None


def test_a_link_grant_or_a_service_key_is_no_bearer_credential(iam, ada):
    grant = _key(
        iam,
        ada,
        kind="grant",
        audience=APP_AUDIENCE,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert credential(grant.value) is None
    with as_service_account("engine"):
        account = iam.create_service_account("ci/nightly")
        service = iam.create_key(account.id)
    assert credential(service.value) is None
    assert credential(created_wrong := "abi_pk_aaaaaaaaaaaaaaaa_nope") is None
    assert created_wrong


# -- revoking all of a user's tokens ---------------------------------------------------------------


def test_revoking_a_users_credentials_cuts_off_what_the_engine_issued_for_them(iam, ada):
    import asyncio

    session = _vouched(iam, ada, SESSION_AUDIENCE)
    with as_service_account("api"):
        delegation = iam.exchange_token(
            TokenExchange(ada.id, TOKEN_TYPE_SESSION, AGENT_AUDIENCE)
        ).token
    api_key = _key(iam, ada)
    coding = _key(iam, ada, audience=CODING_AUDIENCE, resource="http://c:8378")
    link = _key(
        iam,
        ada,
        kind="grant",
        audience=APP_AUDIENCE,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert credential(session) is not None

    assert asyncio.run(credentials.revoke_user_credentials(ada.id)) is True

    # The session and the delegation stop, and so do the link and the agent's
    # key (they would mint new tokens); the user's own API key stays.
    assert credential(session) is None
    with pytest.raises(Exception, match="revoked"):
        iam.verifier().verify(delegation)
    assert credential(coding.value) is None
    assert credential(api_key.value) is not None
    from naas_abi.apps.nexus.apps.api.app.services.apps import links

    assert links.open_link(link.value, APP_AUDIENCE) is None


def test_revoking_a_users_credentials_without_an_engine_is_not_an_error():
    import asyncio

    previous = credentials.configure_iam(lambda: None)
    try:
        assert asyncio.run(credentials.revoke_user_credentials("usr-1")) is False
    finally:
        credentials.configure_iam(previous)


def test_a_failed_revocation_is_reported_and_never_raised(iam, ada, monkeypatch):
    import asyncio

    def boom(*args, **kwargs):
        raise RuntimeError("store down")

    monkeypatch.setattr(iam, "revoke_tokens", boom)
    assert asyncio.run(credentials.revoke_user_credentials(ada.id)) is False
