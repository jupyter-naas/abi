"""Process-wide EventService reference.

EventService is the one piece of engine infrastructure that genuinely needs to
be reachable from anywhere — agents, background threads, library code that has
no engine handle. Every other service is module-scoped and must go through
``EngineProxy`` so dependency declarations stay enforced.

This module deliberately exposes ONLY EventService (not the full engine), so
the singleton can't grow into a back-door to triple_store / cache / secrets /
etc. Modules that need those keep using their proxy.

Set once by ``Engine.load()``. ``set()`` is a plain rebinding (no ContextVar)
so the value is visible across all threads, async tasks, and event loops
regardless of where ``Engine.load()`` ran.

For tests that need to install a fake or temporarily swap the service, use
``with_event_service_override``.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from naas_abi_core.services.event.EventService import EventService


_default_event_service: "EventService | None" = None
_event_service_override: ContextVar["EventService | None"] = ContextVar(
    "event_service_override", default=None
)


def set_default_event_service(service: "EventService | None") -> None:
    """Bind the process-wide EventService. Called by ``Engine.load()``."""
    global _default_event_service
    _default_event_service = service


def get_default_event_service() -> "EventService | None":
    """Return the EventService to use right now, or ``None`` if not configured.

    Checks the per-context override first (for tests / hypothetical
    multi-engine setups), then falls back to the process-wide default.
    """
    return _event_service_override.get() or _default_event_service


@contextmanager
def with_event_service_override(
    service: "EventService | None",
) -> Iterator[None]:
    """Temporarily swap the EventService within this context (and async task)."""
    token = _event_service_override.set(service)
    try:
        yield
    finally:
        _event_service_override.reset(token)
