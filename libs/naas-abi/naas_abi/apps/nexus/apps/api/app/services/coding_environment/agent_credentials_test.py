"""The key a coding environment's agent holds."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi.apps.nexus.apps.api.app.services.coding_environment import agent_credentials
from naas_abi.apps.nexus.apps.api.app.services.openai_gateway.adapters.primary import (
    openai_gateway__primary_adapter__FastAPI as gateway,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.engine.nats_auth import CODING_AUDIENCE
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService

SIDECAR = "http://coder-ada-slides-demo:8378"


@pytest.fixture
def iam():
    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    previous = credentials.configure_iam(lambda: iam)
    yield iam
    credentials.configure_iam(previous)


@pytest.fixture
def ada(iam):
    with as_service_account("engine"):
        iam.put_scope("org-1")
        iam.put_scope("org-1", "ws-1")
        return iam.ensure_user("https://idp.example", "ada")


def credential(value):
    return asyncio.run(credentials.bearer_credential(value))


def test_the_key_is_a_personal_key_for_the_coding_audience_bound_to_the_sidecar(iam, ada):
    value = agent_credentials.mint_agent_key(
        user_id=ada.id, workspace_id="ws-1", sidecar_base=SIDECAR, label="demo"
    )
    assert value.startswith("abi_pk_")
    [record] = iam.store.list_keys(ada.id)
    assert (record.kind, record.audience, record.resource) == (
        "personal",
        CODING_AUDIENCE,
        SIDECAR,
    )
    found = credential(value)
    assert found is not None
    assert (found.kind, found.user_id, found.resource) == ("coding", ada.id, SIDECAR)


def test_it_is_narrowed_to_the_environments_workspace_and_the_platforms_models(iam, ada):
    agent_credentials.mint_agent_key(user_id=ada.id, workspace_id="ws-1", sidecar_base=SIDECAR)
    [record] = iam.store.list_keys(ada.id)
    [statement] = record.scope
    assert statement["effect"] == "Allow" and statement["actions"] == ["*"]
    assert "abi:org-1:ws-1:*" in statement["resources"]
    assert "abi:-:-:model_registry:*" in statement["resources"]
    # Nothing of another workspace, and no IAM administration.
    assert not any(r.startswith("abi:org-1:ws-2") for r in statement["resources"])
    assert not any(":iam:" in r for r in statement["resources"])


def test_a_workspace_iam_does_not_know_gets_the_platforms_models_only(iam, ada):
    agent_credentials.mint_agent_key(
        user_id=ada.id, workspace_id="ws-unknown", sidecar_base=SIDECAR
    )
    [record] = iam.store.list_keys(ada.id)
    assert record.scope[0]["resources"] == [
        "abi:-:-:model_registry:*",
        "abi:-:-:discovery:*",
    ]


def test_it_lives_as_long_as_the_configuration_says_and_never_past_a_year(iam, ada, monkeypatch):
    monkeypatch.setattr(settings, "coding_agent_token_days", 30)
    agent_credentials.mint_agent_key(user_id=ada.id, workspace_id="ws-1", sidecar_base=SIDECAR)
    monkeypatch.setattr(settings, "coding_agent_token_days", 5000)
    agent_credentials.mint_agent_key(
        user_id=ada.id, workspace_id="ws-1", sidecar_base="http://coder-ada-other:8378"
    )
    short, long = sorted(iam.store.list_keys(ada.id), key=lambda k: k.expires_at)
    now = datetime.now(UTC)
    assert timedelta(days=29) < short.expires_at - now <= timedelta(days=31)
    assert long.expires_at - now <= timedelta(days=366)


def test_reprovisioning_revokes_the_environments_earlier_key(iam, ada):
    first = agent_credentials.mint_agent_key(
        user_id=ada.id, workspace_id="ws-1", sidecar_base=SIDECAR
    )
    second = agent_credentials.mint_agent_key(
        user_id=ada.id, workspace_id="ws-1", sidecar_base=SIDECAR
    )
    assert credential(first) is None
    assert credential(second) is not None
    other = agent_credentials.mint_agent_key(
        user_id=ada.id, workspace_id="ws-1", sidecar_base="http://coder-ada-b:8378"
    )
    assert credential(second) is not None and credential(other) is not None


def test_deleting_the_environment_revokes_its_key_and_only_its_key(iam, ada):
    mine = agent_credentials.mint_agent_key(
        user_id=ada.id, workspace_id="ws-1", sidecar_base=SIDECAR
    )
    other = agent_credentials.mint_agent_key(
        user_id=ada.id, workspace_id="ws-1", sidecar_base="http://coder-ada-b:8378"
    )
    assert agent_credentials.revoke_agent_keys(ada.id, SIDECAR) == 1
    assert credential(mine) is None and credential(other) is not None
    assert agent_credentials.revoke_agent_keys(ada.id, SIDECAR) == 0  # nothing left


def test_a_deletion_never_fails_for_a_key(ada, monkeypatch):
    previous = credentials.configure_iam(lambda: None)
    try:
        assert agent_credentials.revoke_agent_keys("usr-1", SIDECAR) == 0
    finally:
        credentials.configure_iam(previous)


def test_an_environment_with_no_sidecar_still_gets_a_key_that_names_no_sidecar(iam, ada):
    value = agent_credentials.mint_agent_key(user_id=ada.id, workspace_id="ws-1", sidecar_base=None)
    found = credential(value)
    assert found is not None and found.resource == f"coding/{ada.id}"


def test_without_the_engine_there_is_no_key():
    previous = credentials.configure_iam(lambda: None)
    try:
        with pytest.raises(agent_credentials.AgentCredentialsUnavailable):
            agent_credentials.mint_agent_key(user_id="u", workspace_id="ws", sidecar_base=SIDECAR)
    finally:
        credentials.configure_iam(previous)


# -- the gateway finds the workspace from the credential, server-side ----------------------------


def _request(credential):
    return SimpleNamespace(state=SimpleNamespace(nexus_credential=credential))


def test_the_gateway_binds_the_workspace_the_coding_key_names(monkeypatch):
    seen = []

    async def sidecar(user_id, base):
        seen.append((user_id, base))
        return base, "the-secret"

    monkeypatch.setattr(gateway, "_sidecar_of", sidecar)
    coding = credentials.Credential(kind="coding", user_id="u-1", resource=SIDECAR)
    assert asyncio.run(gateway._workspace_target(_request(coding))) == (SIDECAR, "the-secret")
    assert seen == [("u-1", SIDECAR)]


@pytest.mark.parametrize(
    "held",
    [
        None,
        credentials.Credential(kind="session", user_id="u-1"),
        credentials.Credential(kind="api-key", user_id="u-1", resource=SIDECAR),
        credentials.Credential(kind="coding", user_id="u-1", resource=None),
    ],
)
def test_any_other_credential_names_no_workspace(monkeypatch, held):
    async def sidecar(user_id, base):
        pytest.fail("a credential that names no sidecar must not look one up")

    monkeypatch.setattr(gateway, "_sidecar_of", sidecar)
    assert asyncio.run(gateway._workspace_target(_request(held))) == (None, None)


def test_a_key_narrowed_to_reading_cannot_make_an_agent_key(iam, ada):
    """The agent key is the user's own, with a scope of its own (the workspace):
    a request that came with a narrower credential must not widen into it."""
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
        agent_credentials.mint_agent_key(
            user_id=ada.id, workspace_id="ws-1", sidecar_base=SIDECAR, label="demo"
        )
    assert iam.store.list_keys(ada.id) == []
