"""Use the first traffic source that starts: traces when a tracing backend is
configured and reachable, else the NATS tap."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable


class FallbackTap:
    def __init__(self, factories: list[Callable[[], Any]]) -> None:
        self._factories = factories
        self._tap: Any = None
        self.source: str | None = None
        self.skipped: dict[str, str] = {}

    async def start(self, emit: Callable[[Any], None]) -> None:
        self.skipped = {}
        for factory in self._factories:
            tap = factory()
            try:
                await tap.start(emit)
            except SourceUnavailable as exc:
                self.skipped[exc.source] = exc.reason
                continue
            self._tap, self.source = tap, getattr(tap, "source", None)
            return
        if len(self.skipped) == 1:
            ((source, reason),) = self.skipped.items()
            raise SourceUnavailable(source, reason)
        raise SourceUnavailable(
            "traffic", "; ".join(f"{source}: {reason}" for source, reason in self.skipped.items())
        )

    async def stop(self) -> None:
        tap, self._tap = self._tap, None
        if tap is not None:
            await tap.stop()
