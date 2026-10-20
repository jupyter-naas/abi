from __future__ import annotations

import jwt
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.factory import (
    CALLER_IDENTITY,
)
from naas_abi_core.engine.nats_auth import ServiceTokenSource


def test_the_service_token_is_reused_until_close_to_expiry():
    """The module caches authorizations by token: a new one per request misses.

    ``build_remote_app_directory`` hands its transports a ``ServiceTokenSource``,
    which reissues a token only once most of its life is gone.
    """
    now = [1_800_000_000.0]
    token = ServiceTokenSource(CALLER_IDENTITY, "s" * 32, clock=lambda: now[0])

    first = token()
    now[0] += 30
    assert token() == first
    now[0] += 55 * 60  # most of the 1 h lifetime is gone
    renewed = token()

    assert renewed != first
    claims = jwt.decode(
        renewed,
        "s" * 32,
        algorithms=["HS256"],
        options={"verify_exp": False, "verify_iat": False, "verify_nbf": False},
    )
    assert claims["sub"] == "api"
