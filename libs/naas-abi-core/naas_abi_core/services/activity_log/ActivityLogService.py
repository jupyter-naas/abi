from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityEvent,
    ActivityLogQuery,
    IActivityLogAdapter,
    IActivityLogDomain,
)
from naas_abi_core.services.ServiceBase import ServiceBase


class ActivityLogService(ServiceBase, IActivityLogDomain):
    """Thin domain wrapper delegating to a secondary adapter.

    Recording failures are swallowed and logged — activity logging must
    never break the call site that produced the event.
    """

    __adapter: IActivityLogAdapter

    def __init__(self, adapter: IActivityLogAdapter) -> None:
        super().__init__()
        self.__adapter = adapter

    def record(self, event: ActivityEvent) -> None:
        try:
            self.__adapter.record(event)
        except Exception as exc:
            from naas_abi_core import logger

            logger.warning(f"activity_log.record failed: {exc}")

    def query(
        self, actor_id: str, query: ActivityLogQuery | None = None
    ) -> list[ActivityEvent]:
        return self.__adapter.query(actor_id, query)

    def list_actors(self) -> list[str]:
        return self.__adapter.list_actors()

    def shutdown(self) -> None:
        self.__adapter.shutdown()
