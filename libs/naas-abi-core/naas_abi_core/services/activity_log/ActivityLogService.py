from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityEvent,
    ActivityLogQuery,
    IActivityLogAdapter,
    IActivityLogDomain,
)
from naas_abi_core.services.ServiceBase import ServiceBase

if TYPE_CHECKING:
    from naas_abi_core.engine.IEngine import IEngine


class ActivityLogService(ServiceBase, IActivityLogDomain):
    """Thin domain wrapper delegating to a secondary adapter.

    Recording failures are swallowed and logged — activity logging must
    never break the call site that produced the event.
    """

    __adapter: IActivityLogAdapter

    def __init__(self, adapter: IActivityLogAdapter) -> None:
        super().__init__()
        self.__adapter = adapter

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
            self.__adapter.record(event)
        except Exception as exc:  # noqa: BLE001
            from naas_abi_core import logger

            logger.warning(f"activity_log.record failed: {exc}")

    def query(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> list[ActivityEvent]:
        return self.__adapter.query(actor_id, query)

    @contextmanager
    def query_stream(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> Iterator[Iterator[ActivityEvent]]:
        with self.__adapter.query_stream(actor_id, query) as events:
            yield events

    def list_actors(self) -> list[str]:
        return self.__adapter.list_actors()

    def shutdown(self) -> None:
        self.__adapter.shutdown()
