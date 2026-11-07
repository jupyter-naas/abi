"""The credential a coding environment's agent holds.

The agent in a workspace (the Continue extension) talks to the OpenAI gateway as
the user who owns the environment. It holds a *personal key* of that user
(``abi_pk_``), made for this environment alone:

* its audience is ``abi:delegated:coding``: the gateway (``/api/v1/*``) takes it,
  no other route and not the WebSocket does, and it is never a session;
* it is bound to the environment's sidecar (``resource``, its base URL), so the
  gateway finds the workspace's exec sidecar server-side and never from a
  request;
* it is narrowed (``abi_scope``) to what an agent of that workspace needs: the
  workspace's own resources and the platform's models and agents;
* it is stored hashed, expires with the configured lifetime (a year at most),
  is revoked with the environment, and ends with its owner.

It replaces the thirty-day session token the environments were given, which
opened every route as the user.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi.apps.nexus.apps.api.app.services.iam.names import SERVICE as NEXUS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import WORKSPACE
from naas_abi_core import logger
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    service_account,
    use_call_context,
    user,
)
from naas_abi_core.engine.nats_auth import CODING_AUDIENCE
from naas_abi_core.services.iam.names import PLATFORM, below

MAX_DAYS = 365


class AgentCredentialsUnavailable(RuntimeError):
    """IAM is not there to make the agent's key (an engine-less process)."""


def agent_scope(container: str | None) -> tuple[dict[str, Any], ...]:
    """What an agent of a workspace (its ``container``) may do: everything in
    that workspace, and use the platform's models and agents. A workspace IAM
    does not know (None) has the platform's only."""
    resources = [f"{PLATFORM}model_registry:*", f"{PLATFORM}discovery:*"]
    if container:
        resources[:0] = [container, below(container)]
    return ({"effect": "Allow", "actions": ["*"], "resources": resources},)


def _iam() -> Any:
    iam = credentials.IAM()
    if iam is None:
        raise AgentCredentialsUnavailable("An agent's key needs the engine's IAM")
    return iam


def _acting_for(user_id: str) -> CallContext:
    credentials.refuse_a_limited_credential("make a key for a coding agent")
    return CallContext(principal=service_account("api"), on_behalf_of=user(user_id))


def environment_resource(user_id: str, sidecar_base: str | None) -> str:
    """What a key is bound to: the sidecar of the environment, or, for one with no
    sidecar, a name that matches no environment."""
    return sidecar_base or f"coding/{user_id}"


def mint_agent_key(
    *,
    user_id: str,
    workspace_id: str | None,
    sidecar_base: str | None,
    label: str = "",
) -> str:
    """The key a new (or reprovisioned) environment's agent holds. Keys earlier
    made for the same environment are revoked first: one environment, one key."""
    iam = _iam()
    resource = environment_resource(user_id, sidecar_base)
    container = iam.container(NEXUS, WORKSPACE, workspace_id) if workspace_id else None
    days = max(1, min(settings.coding_agent_token_days, MAX_DAYS))
    with use_call_context(_acting_for(user_id)):
        _revoke_for(iam, user_id, resource)
        created = iam.create_key(
            user_id,
            description=f"coding agent: {label or resource}"[:200],
            audience=CODING_AUDIENCE,
            resource=resource,
            scope=agent_scope(container),
            expires_at=datetime.now(UTC) + timedelta(days=days),
        )
    return created.value


def _revoke_for(iam: Any, user_id: str, resource: str) -> int:
    revoked = 0
    for key in iam.list_keys(user_id):
        if key.audience == CODING_AUDIENCE and key.resource == resource and key.revoked_at is None:
            iam.revoke_key(user_id, key.key_id)
            revoked += 1
    return revoked


def revoke_agent_keys(user_id: str, sidecar_base: str | None) -> int:
    """Revoke the keys of an environment that is going away. Best effort and
    quiet: a key that cannot be revoked still expires, and the owner can
    revoke it from their API keys."""
    iam = credentials.IAM()
    if iam is None:
        return 0
    try:
        with as_service_account("api"):
            return _revoke_for(iam, user_id, environment_resource(user_id, sidecar_base))
    except Exception as exc:  # noqa: BLE001 - never fail a deletion on a key
        logger.warning(f"Coding agent keys of {user_id} were not revoked: {exc}")
        return 0


async def amint_agent_key(**fields: Any) -> str:
    return await asyncio.to_thread(mint_agent_key, **fields)


async def arevoke_agent_keys(user_id: str, sidecar_base: str | None) -> int:
    return await asyncio.to_thread(revoke_agent_keys, user_id, sidecar_base)
