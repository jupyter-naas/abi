"""Backoff with full jitter, for everything that retries the broker.

A module host runs dozens of modules, one NATS connection each. When the broker
or the engine's auth callout is slow (an engine restart, a burst of sign-ins),
they all lose it at the same moment. Retrying at a fixed pace, they also come
back at the same moment, the callout answers too late again, and the host
keeps the broker in a storm of failed sign-ins. Waiting a random time below a
ceiling that doubles with each failed attempt spreads them out.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

BASE_SECONDS = 0.5
"""The ceiling of the first retry."""
CAP_SECONDS = 30.0
"""The longest wait between two retries."""


def backoff_delay(
    attempt: int,
    *,
    base: float = BASE_SECONDS,
    cap: float = CAP_SECONDS,
    rng: Callable[[], float] | None = None,
) -> float:
    """How long to wait before retry ``attempt`` (0 for the first): a random time
    between 0 and ``min(cap, base * 2 ** attempt)`` ("full jitter")."""
    exponent = min(max(attempt, 0), 32)  # 2 ** 32 * base is far above any cap
    ceiling = min(cap, base * 2**exponent)
    return ceiling * (rng or random.random)()


def jittered_interval(
    seconds: float, *, spread: float = 0.25, rng: Callable[[], float] | None = None
) -> float:
    """``seconds`` shortened by up to ``spread`` of itself, at random: a periodic
    task started at the same moment in many processes drifts apart, and never
    waits longer than ``seconds``."""
    return seconds * (1.0 - spread * (rng or random.random)())


def reconnect_backoff_handler(
    *, base: float = BASE_SECONDS, cap: float = CAP_SECONDS
) -> Callable[[list[Any], dict[str, Any]], tuple[Any, float]]:
    """A nats-py ``reconnect_to_server_handler``: before each reconnect attempt,
    nats-py waits the delay it returns. The attempt number is the most failed
    attempts of any server (nats-py counts them, and resets a server's count
    once it connects). The server is left to nats-py (``None``)."""

    def handler(servers: list[Any], server_info: dict[str, Any]) -> tuple[Any, float]:
        attempt = max((getattr(s, "reconnects", 0) or 0 for s in servers), default=0)
        return None, backoff_delay(attempt, base=base, cap=cap)

    return handler


__all__ = [
    "BASE_SECONDS",
    "CAP_SECONDS",
    "backoff_delay",
    "jittered_interval",
    "reconnect_backoff_handler",
]
