"""Requests to the engine that ride out a handover.

One engine serves the kernel services and discovery, on queue groups. While it
hands over to the next one during a deploy, or restarts, a request can briefly
find nobody subscribed. The broker then answers "no responders" without
delivering it, so sending it again is always safe. See ABI's
docs/adr/20261006_single-serving-engine.md.

Subjects of one instance (presence, agents, transfer sessions) are not retried:
nobody answering there means the instance is gone. A transfer's open is the
exception among its calls: it goes to the engine's queue group.
"""

from __future__ import annotations

import asyncio
from typing import Any

from nats.errors import NoRespondersError

RETRY_SECONDS = 5.0
_FIRST_DELAY_SECONDS = 0.05
_MAX_DELAY_SECONDS = 0.5
# The last try lands this long before the caller's deadline, so it sees "no
# responders" (nobody serves the subject) and not a timeout.
_DEADLINE_MARGIN_SECONDS = 0.5


def engine_served(subject: str) -> bool:
    """Whether the serving engine answers ``subject`` (on a queue group)."""
    if subject.startswith("abi.svc."):
        return True
    return subject.startswith("abi.discovery.") and ".presence." not in subject


def transfer_open(subject: str) -> bool:
    """Whether ``subject`` opens a transfer (``<prefix>.open``). The open goes to
    the serving engine's queue group; the session's later calls go to the one
    engine that opened it (``<prefix>.<owner>.<operation>``)."""
    return subject.endswith(".transfer.open")


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
    when the engine serves ``subject``. The retries stop just short of
    ``timeout``, the caller's own deadline."""
    if not engine_served(subject):
        return await nc.request(subject, payload, timeout=timeout, headers=headers)
    loop = asyncio.get_running_loop()
    give_up = loop.time() + min(retry_seconds, timeout - _DEADLINE_MARGIN_SECONDS)
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
