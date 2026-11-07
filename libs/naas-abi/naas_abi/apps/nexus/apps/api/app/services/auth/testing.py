"""Credentials for the tests of routes: what the engine would have issued."""

from __future__ import annotations

from typing import Any

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.engine.nats_auth import SESSION_AUDIENCE
from naas_abi_core.services.iam.IAMPorts import TOKEN_TYPE_SESSION, TokenExchange


def session_token(iam: Any, user_id: str) -> str:
    """A session token of ``user_id`` (``abi:session``, ES256), as Nexus gets one
    for a user an identity provider vouched for."""
    with as_service_account("api"):
        return iam.exchange_token(
            TokenExchange(user_id, TOKEN_TYPE_SESSION, SESSION_AUDIENCE)
        ).token
