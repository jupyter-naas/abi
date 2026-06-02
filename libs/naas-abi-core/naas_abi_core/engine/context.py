"""Process-wide engine service references.

Two services in this module are intentionally exposed as process-wide
singletons because they genuinely need to be reachable from anywhere —
agents, background threads, library code that has no engine handle:

* **EventService** — the cross-cutting event bus.
* **ModelRegistry** — the global catalog of chat / embedding models. The
  registry is *by design* a catalog every consumer can query (vs.
  module-scoped services like triple_store / cache / secrets which respect
  ``ModuleDependencies`` access control), so a global accessor doesn't
  weaken the dependency model.

Every other service stays behind ``EngineProxy`` so dependency declarations
stay enforced. Do not add anything else here without a similar argument.

Set once by ``Engine.load()``. ``set_*()`` performs plain rebinding (no
ContextVar) so the value is visible across all threads, async tasks, and
event loops regardless of where ``Engine.load()`` ran.

For tests that need to install a fake or temporarily swap a service, use
the ``with_*_override`` context managers.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from naas_abi_core.services.event.EventService import EventService
    from naas_abi_core.services.model_registry.ModelRegistryPort import (
        IModelRegistry,
    )


# --------------------------------------------------------------------------- #
# EventService                                                                 #
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# ModelRegistry                                                                #
# --------------------------------------------------------------------------- #


_default_model_registry: "IModelRegistry | None" = None
_model_registry_override: ContextVar["IModelRegistry | None"] = ContextVar(
    "model_registry_override", default=None
)


def set_default_model_registry(registry: "IModelRegistry | None") -> None:
    """Bind the process-wide ModelRegistry. Called by ``Engine.load()``."""
    global _default_model_registry
    _default_model_registry = registry


def get_default_model_registry() -> "IModelRegistry | None":
    """Return the ModelRegistry to use right now, or ``None`` if not configured.

    Checks the per-context override first, then falls back to the
    process-wide default.
    """
    return _model_registry_override.get() or _default_model_registry


@contextmanager
def with_model_registry_override(
    registry: "IModelRegistry | None",
) -> Iterator[None]:
    """Temporarily swap the ModelRegistry within this context (and async task)."""
    token = _model_registry_override.set(registry)
    try:
        yield
    finally:
        _model_registry_override.reset(token)
