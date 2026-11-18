"""Reconnects, renewals and failed fetches back off with jitter: a host of many
modules that all lose the broker at once must not come back at once."""

from __future__ import annotations

import asyncio
import random
from types import SimpleNamespace

from naas_abi_sdk import job_host as job_host_module
from naas_abi_sdk.backoff import backoff_delay, jittered_interval
from naas_abi_sdk.transport import Transport


def test_the_ceiling_doubles_from_the_base_up_to_the_cap():
    ceilings = [backoff_delay(n, base=0.5, cap=30.0, rng=lambda: 1.0) for n in range(9)]
    assert ceilings == [0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 30.0]


def test_full_jitter_spreads_each_delay_between_zero_and_its_ceiling():
    rng = random.Random(7).random
    delays = [backoff_delay(4, base=0.5, cap=30.0, rng=rng) for _ in range(500)]
    assert all(0.0 <= d <= 8.0 for d in delays)
    assert min(delays) < 1.0 and max(delays) > 7.0  # spread over the window
    assert backoff_delay(4, rng=lambda: 0.0) == 0.0


def test_a_huge_attempt_count_stays_at_the_cap():
    assert backoff_delay(10_000, base=0.5, cap=30.0, rng=lambda: 1.0) == 30.0
    assert backoff_delay(-3, base=0.5, cap=30.0, rng=lambda: 1.0) == 0.5


def test_a_jittered_interval_is_only_ever_shortened():
    assert jittered_interval(120.0, spread=0.25, rng=lambda: 0.0) == 120.0
    assert jittered_interval(120.0, spread=0.25, rng=lambda: 1.0) == 90.0
    rng = random.Random(3).random
    intervals = [jittered_interval(120.0, spread=0.25, rng=rng) for _ in range(200)]
    assert all(90.0 <= i <= 120.0 for i in intervals)
    assert len(set(intervals)) > 100


# --- the transport ---------------------------------------------------------------


def _connect_options(monkeypatch, **transport_options):
    from nats.aio.client import Client

    captured: dict = {}

    async def connect(self, servers, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(Client, "connect", connect)
    transport = Transport("nats://unused", "issued", **transport_options)
    asyncio.run(transport.connect())
    return captured


def test_reconnects_wait_a_jittered_backoff_that_grows_with_failed_attempts(monkeypatch):
    handler = _connect_options(monkeypatch)["reconnect_to_server_handler"]
    monkeypatch.setattr(random, "random", lambda: 1.0)
    server = SimpleNamespace(uri=None, reconnects=0)
    waits = []
    for attempts in range(8):
        server.reconnects = attempts
        selected, delay = handler([server], {})
        assert selected is None  # nats-py keeps choosing the server
        waits.append(delay)
    assert waits == [backoff_delay(n, rng=lambda: 1.0) for n in range(8)]
    assert waits[0] <= 1.0 and waits[-1] == 30.0

    monkeypatch.setattr(random, "random", lambda: 0.25)
    assert handler([SimpleNamespace(uri=None, reconnects=3)], {})[1] == 0.25 * backoff_delay(
        3, rng=lambda: 1.0
    )


def test_a_callers_own_reconnect_handler_is_kept(monkeypatch):
    def mine(servers, info):
        return None, 0.0

    options = _connect_options(monkeypatch, reconnect_to_server_handler=mine)
    assert options["reconnect_to_server_handler"] is mine


def test_renewals_are_spread_below_their_interval(monkeypatch):
    transport = Transport("nats://unused", "issued", renew_seconds=120.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    assert transport._renew_delay() == 120.0
    monkeypatch.setattr(random, "random", lambda: 1.0)
    assert 60.0 <= transport._renew_delay() < 120.0


# --- the job host's fetch loop ---------------------------------------------------


def test_a_failing_fetch_backs_off_more_each_time_and_resets_after_a_fetch(monkeypatch):
    from unittest.mock import AsyncMock

    from nats.errors import OutboundBufferLimitError

    host = job_host_module.JobHost(AsyncMock(), AsyncMock(), "acme", "default", {})
    attempts: list[int] = []

    def delay(attempt: int, **kwargs) -> float:
        attempts.append(attempt)
        return 0.0

    monkeypatch.setattr(job_host_module, "backoff_delay", delay)
    outcomes = [OutboundBufferLimitError()] * 4 + [[]] + [OutboundBufferLimitError()]

    class Subscription:
        async def fetch(self, batch, timeout=None):
            if not outcomes:
                host._closing = True
                return []
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    descriptor = SimpleNamespace(name="sync", max_concurrency=1)
    asyncio.run(asyncio.wait_for(host._consume(Subscription(), descriptor, None), 5))
    assert attempts == [0, 1, 2, 3, 0]
