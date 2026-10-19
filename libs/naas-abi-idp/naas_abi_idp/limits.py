"""Rate limits kept in the provider's own documents.

A counter is one document, so counting an attempt and refusing the next are one
compare-and-set: parallel guesses cannot all slip under the limit. Sign-in
guesses are counted *before* they are judged and given back on success, so a
burst of parallel requests spends the same budget as a sequence.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable

from naas_abi_idp.models import RATE_LIMITS
from naas_abi_idp.ports import DocumentStore, RateLimited

_ATTEMPTS = 8  # compare-and-set retries under contention


class RateLimiter:
    def __init__(
        self,
        store: DocumentStore,
        window_seconds: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store, self._window, self._clock = store, window_seconds, clock

    @staticmethod
    def _id(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def consume(self, key: str, limit: int) -> int:
        """Count one attempt of ``key``; ``RateLimited`` when ``limit`` attempts
        already happened in the window. Returns the attempts left."""
        id = self._id(key)
        for _ in range(_ATTEMPTS):
            now = self._clock()
            doc = self._store.get(RATE_LIMITS, id)
            events = [
                t for t in (doc.data["events"] if doc else []) if now - t < self._window
            ]
            if len(events) >= limit:
                raise RateLimited(max(1, int(events[0] + self._window - now) + 1))
            events.append(now)
            data = {"events": events}
            written = (
                self._store.replace(doc, RATE_LIMITS, data)
                if doc is not None
                else self._store.create(RATE_LIMITS, id, data)
            )
            if written is not None:
                return limit - len(events)
        raise RateLimited(self._window)  # contended past the retries: refuse

    def refund(self, key: str) -> None:
        """Give back the newest attempt of ``key`` (a sign-in that succeeded)."""
        id = self._id(key)
        for _ in range(_ATTEMPTS):
            doc = self._store.get(RATE_LIMITS, id)
            if doc is None or not doc.data["events"]:
                return
            data = {"events": doc.data["events"][:-1]}
            if self._store.replace(doc, RATE_LIMITS, data) is not None:
                return

    def reset(self, key: str) -> None:
        self._store.delete(RATE_LIMITS, self._id(key))

    def purge(self, now: float | None = None) -> int:
        """Delete the counters with no attempt left in the window."""
        now = self._clock() if now is None else now
        removed, after = 0, None
        while True:
            page = self._store.find(RATE_LIMITS, limit=200, after=after)
            for doc in page.items:
                if all(now - t >= self._window for t in doc.data["events"]):
                    removed += self._store.delete(
                        RATE_LIMITS, doc.id, version=doc.version
                    )
            after = page.cursor
            if after is None:
                return removed
