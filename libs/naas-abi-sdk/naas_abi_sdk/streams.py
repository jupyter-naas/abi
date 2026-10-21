"""Streams a module uses but may not create.

Logged in as the broker user ``module``, a module may not create or update a JetStream
stream (naas_abi_core.engine.nats_permissions): the engine creates them. The broker
answers such a request with nothing, so the JetStream call times out;
:func:`not_created` turns that into an error that says why and who must create it.
"""

from __future__ import annotations

import asyncio

from nats.errors import TimeoutError as NATSTimeoutError

# What a module's create or update of a stream gets when the broker refuses it.
REFUSED = (NATSTimeoutError, asyncio.TimeoutError)


class StreamNotCreated(RuntimeError):
    """A stream the module needs is missing or out of date, and it could not
    create or update it."""


def not_created(kind: str, name: str, cause: BaseException) -> StreamNotCreated:
    return StreamNotCreated(
        f"{kind} {name!r} is missing or out of date, and creating or updating it got "
        f"no answer ({type(cause).__name__}). Logged in as the broker user `module`, "
        "a module may not create or update streams: the engine hosting discovery "
        "creates the jobs stream and the claim-check store at start "
        "(naas_abi_core.engine.nats_permissions.prepare_module_streams), and a bus "
        "queue's stream must be created by the engine."
    )
