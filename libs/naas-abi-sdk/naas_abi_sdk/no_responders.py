"""Requests to the engine that ride out a handover.

One engine serves the kernel services and discovery, on queue groups. While it
hands over to the next one during a deploy, or restarts, a request can briefly
find nobody subscribed. The broker then answers "no responders" without
delivering it, so sending it again is always safe. See ABI's
docs/adr/20261006_single-serving-engine.md.

Subjects of one instance (presence, agents, transfer sessions) are not retried:
nobody answering there means the instance is gone.
"""

from __future__ import annotations

import asyncio
from typing import Any

from nats.errors import NoRespondersError

RETRY_SECONDS = 5.0
_FIRST_DELAY_SECONDS = 0.05
_MAX_DELAY_SECONDS = 0.5


def engine_served(subject: str) -> bool:
    """Whether the serving engine answers ``subject`` (on a queue group)."""
    if subject.startswith("abi.svc."):
        return True
    return subject.startswith("abi.discovery.") and ".presence." not in subject


async def request(
    nc: Any,
    subject: str,
    payload: bytes,
    *,
    headers: dict[str, str],
    timeout: float,
    retry_seconds: float = RETRY_SECONDS,
) -> Any:
    """``nc.request``, sent again on "no responders" for up to ``retry_seconds``
    when the engine serves ``subject``. The caller's own deadline still applies."""
    if not engine_served(subject):
        return await nc.request(subject, payload, timeout=timeout, headers=headers)
    loop = asyncio.get_running_loop()
    give_up = loop.time() + retry_seconds
    delay = _FIRST_DELAY_SECONDS
    while True:
        try:
            return await nc.request(subject, payload, timeout=timeout, headers=headers)
        except NoRespondersError:
            remaining = give_up - loop.time()
            if remaining <= 0:
                raise
            await asyncio.sleep(min(delay, remaining))  # the last try ends the window
            delay = min(delay * 2, _MAX_DELAY_SECONDS)
