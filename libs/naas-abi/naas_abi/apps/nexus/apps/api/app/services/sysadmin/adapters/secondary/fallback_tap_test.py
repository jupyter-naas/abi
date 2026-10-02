import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.fallback_tap import (
    FallbackTap,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable


class _Tap:
    def __init__(self, source, fail=None):
        self.source, self.fail, self.started, self.stopped = source, fail, False, False

    async def start(self, emit):
        if self.fail:
            raise SourceUnavailable(self.source, self.fail)
        self.started = True

    async def stop(self):
        self.stopped = True


def test_the_first_available_source_is_used():
    traces, nats = _Tap("traces"), _Tap("nats")
    tap = FallbackTap([lambda: traces, lambda: nats])

    asyncio.run(tap.start(lambda e: None))
    asyncio.run(tap.stop())

    assert tap.source == "traces" and traces.started and traces.stopped and not nats.started


def test_falls_back_when_the_preferred_source_is_down():
    tap = FallbackTap([lambda: _Tap("traces", "refused"), lambda: _Tap("nats")])

    asyncio.run(tap.start(lambda e: None))

    assert tap.source == "nats"
    assert tap.skipped == {"traces": "refused"}


def test_every_source_down_is_unavailable_with_all_reasons():
    tap = FallbackTap([lambda: _Tap("traces", "refused"), lambda: _Tap("nats", "NATS mode is off")])

    with pytest.raises(SourceUnavailable) as raised:
        asyncio.run(tap.start(lambda e: None))
    assert "refused" in raised.value.reason and "NATS mode is off" in raised.value.reason
