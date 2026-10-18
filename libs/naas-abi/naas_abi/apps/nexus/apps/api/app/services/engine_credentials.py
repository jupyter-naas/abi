"""The ``api`` service account's tokens, for Nexus's own NATS calls.

Nexus runs in the serving engine: IAM signs its tokens in this process
(``Engine.service_credentials``). Nothing here holds a signing secret.
"""

from __future__ import annotations

from typing import Any

# Discovery binds invocation status/events/cancel to the caller identity; every
# API worker shares this one so any worker can follow a run another started.
CALLER_IDENTITY = "api"


def api_token() -> Any:
    """A callable returning a valid ``api`` token, for ``Transport``. The
    engine is looked up when a token is needed, not when a client is built."""

    def token() -> str:
        from naas_abi import ABIModule

        engine = ABIModule.get_instance().engine
        return engine.service_credentials(CALLER_IDENTITY).token()

    return token
