"""The ``api`` service account's tokens, for Nexus's own NATS calls.

Nexus runs in the serving engine: IAM signs its tokens in this process
(``Engine.service_credentials``). Nothing here holds a signing secret.
"""

from __future__ import annotations

from typing import Any

# The service account Nexus's own NATS calls are made as (its token, ``api_token``)
# and that vouches for the signed-in users it serves: IAM exchanges for them as
# ``api`` (``api_delegate``). Discovery binds a run to the user it was started
# for, so any API worker can follow a run another started.
CALLER_IDENTITY = "api"


def api_token() -> Any:
    """A callable returning a valid ``api`` token, for ``Transport``. The
    engine is looked up when a token is needed, not when a client is built."""

    def token() -> str:
        from naas_abi import ABIModule

        engine = ABIModule.get_instance().engine
        return engine.service_credentials(CALLER_IDENTITY).token()

    return token


def api_delegate() -> Any:
    """What ``Transport(delegate=...)`` calls to carry the signed-in user the
    request acts for: a delegation (``abi:delegated:agent``, RFC §9.4) naming
    ``api`` as the actor for a kernel service, or the module behind the host
    being called. IAM signs it in this process and refuses a user it
    suspended: such a call fails, it is never made as ``api`` alone. Replaces
    the ``Abi-On-Behalf-Of`` header, which the kernel no longer accepts."""

    def delegate(user: Any, recipient: str | None = None) -> str:
        from naas_abi import ABIModule

        engine = ABIModule.get_instance().engine
        return str(engine.service_credentials(CALLER_IDENTITY).token_for(user, recipient))

    return delegate


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
