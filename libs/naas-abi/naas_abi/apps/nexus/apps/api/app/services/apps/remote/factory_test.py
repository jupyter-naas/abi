from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.factory import ServiceToken


def test_the_service_token_is_reused_until_close_to_expiry():
    """The module caches authorizations by token: a new one per request misses."""
    now = [datetime(2026, 10, 12, 12, 0, tzinfo=UTC)]
    token = ServiceToken("s" * 32, clock=lambda: now[0])

    first = token()
    now[0] += timedelta(seconds=30)
    assert token() == first
    now[0] += timedelta(minutes=55)  # within 5 minutes of the 1 h expiry
    renewed = token()

    assert renewed != first
    claims = jwt.decode(
        renewed, "s" * 32, algorithms=["HS256"], options={"verify_exp": False}
    )
    assert claims["sub"] == "api"
