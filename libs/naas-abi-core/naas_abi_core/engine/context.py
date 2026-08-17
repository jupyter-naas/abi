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

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from naas_abi_core.services.event.EventService import EventService
    from naas_abi_core.services.gatekeeper.GatekeeperService import GatekeeperService
    from naas_abi_core.services.model_registry.ModelRegistryPort import (
        IModelRegistry,
    )


# --------------------------------------------------------------------------- #
# EventService                                                                 #
# --------------------------------------------------------------------------- #


_default_event_service: EventService | None = None
_event_service_override: ContextVar[EventService | None] = ContextVar(
    "event_service_override", default=None
)


def set_default_event_service(service: EventService | None) -> None:
    """Bind the process-wide EventService. Called by ``Engine.load()``."""
    global _default_event_service
    _default_event_service = service


def get_default_event_service() -> EventService | None:
    """Return the EventService to use right now, or ``None`` if not configured.

    Checks the per-context override first (for tests / hypothetical
    multi-engine setups), then falls back to the process-wide default.
    """
    return _event_service_override.get() or _default_event_service


@contextmanager
def with_event_service_override(
    service: EventService | None,
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


_default_model_registry: IModelRegistry | None = None
# Flips to True the moment ``Engine.load()`` finishes binding (or explicitly
# clearing) the singleton — i.e. after every module's ``on_load`` has run and
# after ``validate_defaults``. Until then, ``get_default_model_registry()``
# raises rather than returning a half-populated registry. This is what fences
# off the common footgun of a module reaching for the global accessor from
# inside its own ``on_load`` and getting back a registry that has only
# whatever modules happened to have loaded so far.
_default_model_registry_ready: bool = False
_model_registry_override: ContextVar[IModelRegistry | None] = ContextVar(
    "model_registry_override", default=None
)


def set_default_model_registry(registry: IModelRegistry | None) -> None:
    """Bind (or unbind) the process-wide ModelRegistry and mark it ready.

    Called by ``Engine.load()`` exactly once per load, after every module's
    ``on_load`` has finished and after ``validate_defaults``. Module code must
    not call this directly. Passing ``None`` records "this engine has no
    registry" — a valid post-init state, distinct from "the engine hasn't
    loaded yet" (which keeps the ready flag False).
    """
    global _default_model_registry, _default_model_registry_ready
    _default_model_registry = registry
    _default_model_registry_ready = True


def get_default_model_registry() -> IModelRegistry | None:
    """Return the process-wide ModelRegistry, or ``None`` if the engine has
    no registry configured.

    Raises ``RuntimeError`` if called before ``Engine.load()`` has finished
    binding the singleton — typically because a module's ``on_load`` reached
    for the registry through this accessor instead of via
    ``self._engine.services.model_registry``. During ``on_load`` use the
    proxy; this global accessor is for ``on_initialized`` hooks and
    request-time / runtime code, where every module is guaranteed to have
    already registered.

    The per-context override (used by tests / hypothetical multi-engine
    setups) bypasses the ready check, so test fixtures can install a fake
    without going through Engine.load.
    """
    override = _model_registry_override.get()
    if override is not None:
        return override
    if not _default_model_registry_ready:
        raise RuntimeError(
            "Process-wide ModelRegistry is not ready: get_default_model_registry() "
            "was called before Engine.load() finished loading all modules. Module "
            "on_load callbacks must use self._engine.services.model_registry "
            "instead — the global accessor is intentionally fenced off until "
            "after on_load completes so callers can trust the registry is fully "
            "populated."
        )
    return _default_model_registry


@contextmanager
def with_model_registry_override(
    registry: IModelRegistry | None,
) -> Iterator[None]:
    """Temporarily swap the ModelRegistry within this context (and async task)."""
    token = _model_registry_override.set(registry)
    try:
        yield
    finally:
        _model_registry_override.reset(token)


# --------------------------------------------------------------------------- #
# GatekeeperService                                                            #
# --------------------------------------------------------------------------- #


_default_gatekeeper_service: GatekeeperService | None = None
_gatekeeper_service_override: ContextVar[GatekeeperService | None] = ContextVar(
    "gatekeeper_service_override", default=None
)


def set_default_gatekeeper_service(service: GatekeeperService | None) -> None:
    """Bind the process-wide GatekeeperService. Called by ``Engine.load()``."""
    global _default_gatekeeper_service
    _default_gatekeeper_service = service


def get_default_gatekeeper_service() -> GatekeeperService | None:
    """Return the GatekeeperService to use right now, or ``None`` if not configured."""
    return _gatekeeper_service_override.get() or _default_gatekeeper_service


@contextmanager
def with_gatekeeper_service_override(
    service: GatekeeperService | None,
) -> Iterator[None]:
    """Temporarily swap the GatekeeperService within this context (and async task)."""
    token = _gatekeeper_service_override.set(service)
    try:
        yield
    finally:
        _gatekeeper_service_override.reset(token)


def init_default_gatekeeper_service(
    data_dir: str = "storage/gatekeeper",
) -> GatekeeperService:
    """Create and bind the default SQLite-backed gatekeeper (idempotent)."""
    global _default_gatekeeper_service
    if _default_gatekeeper_service is None:
        from naas_abi_core.services.gatekeeper.GatekeeperFactory import (
            GatekeeperFactory,
        )

        _default_gatekeeper_service = GatekeeperFactory.GatekeeperServiceSqlite(
            data_dir=data_dir
        )
    return _default_gatekeeper_service
