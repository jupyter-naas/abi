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


def api_host_token() -> Any:
    """A function of a host's ``<sa>`` returning a valid ``api`` token addressed
    to that host alone, for ``Transport(host_token=...)``.

    Nexus calls remote agents, apps and models with these: a host reads the
    token of each request and may forward it to discovery, which accepts it from
    the host it names only, and the kernel services refuse it. Never hand a host
    ``api_token()``, nor one made for another host: ``api`` may do everything."""

    def token(recipient: str) -> str:
        from naas_abi import ABIModule
        from naas_abi_core.engine.nats_auth import host_audience

        engine = ABIModule.get_instance().engine
        return engine.service_credentials(
            CALLER_IDENTITY, audience=host_audience(recipient)
        ).token()

    return token
