from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from naas_abi_core.engine.call_context import call_subject
from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityEvent,
    ActivityLogQuery,
    IActivityLogAdapter,
    IActivityLogDomain,
)
from naas_abi_core.services.activity_log.iam_catalog import CATALOG
from naas_abi_core.services.iam.guard import ServiceGuard
from naas_abi_core.services.ServiceBase import ServiceBase

if TYPE_CHECKING:
    from naas_abi_core.engine.IEngine import IEngine


def call_actor() -> str | None:
    """The actor of the current call (``call_subject``), RFC §10.1."""
    return call_subject()


class ActivityLogService(ServiceBase, IActivityLogDomain):
    """Thin domain wrapper delegating to a secondary adapter.

    Recording failures are swallowed and logged — activity logging must
    never break the call site that produced the event.

    Wired with IAM (an owner), every operation is authorized against the
    ``activity_log`` catalog on ``actor/<principal id>``. A recorded event's
    actor is the call's (``call_actor``), never the event's ``actor_id``: an
    anonymous call records nothing. A facade over NATS is not wired, and the
    owner it calls checks and names the actor.
    """

    __adapter: IActivityLogAdapter

    def __init__(self, adapter: IActivityLogAdapter) -> None:
        super().__init__()
        self.__adapter = adapter
        self._guard = ServiceGuard.of(CATALOG, self)

    def set_services(self, services: IEngine.Services) -> None:
        """Also hand the engine's services to an adapter built on one of them
        (the ``document`` adapter), as ``CacheService`` does."""
        super().set_services(services)
        if hasattr(self.__adapter, "wire_services"):
            self.__adapter.wire_services(services)

    @property
    def adapter(self) -> IActivityLogAdapter:
        """The wrapped secondary adapter -- public so callers (e.g.
        ``EngineNATSLoader``) can check what kind of adapter this service is
        backed by, mirroring ``ObjectStorageService.adapter``."""
        return self.__adapter

    def record(self, event: ActivityEvent) -> None:
        try:
            if self._guard.enforcing:
                actor = call_actor()
                if actor is None:
                    from naas_abi_core import logger

                    logger.debug("activity_log.record: anonymous call, not recorded")
                    return
                event = event.model_copy(update={"actor_id": actor})
                self._guard.require("Record", "actor", actor)
            self.__adapter.record(event)
        except Exception as exc:  # noqa: BLE001
            from naas_abi_core import logger

            logger.warning(f"activity_log.record failed: {exc}")

    def query(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> list[ActivityEvent]:
        self._guard.require("Query", "actor", actor_id)
        return self.__adapter.query(actor_id, query)

    @contextmanager
    def query_stream(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> Iterator[Iterator[ActivityEvent]]:
        self._guard.require("QueryStream", "actor", actor_id)
        with self.__adapter.query_stream(actor_id, query) as events:
            yield events

    def list_actors(self) -> list[str]:
        """The actors the caller may list."""
        return self._guard.filter(
            "ListActors", "actor", self.__adapter.list_actors(), lambda actor: actor
        )

    def shutdown(self) -> None:
        self._guard.require("Shutdown", "service")
        self.__adapter.shutdown()
