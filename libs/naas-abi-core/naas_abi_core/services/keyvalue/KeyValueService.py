from naas_abi_core import logger
from naas_abi_core.services.keyvalue.KeyValuePorts import IKeyValueAdapter
from naas_abi_core.services.keyvalue.ontologies.modules.KeyValueEventOntology import (
    KeyValueDeleted,
    KeyValueError,
    KeyValueSet,
)
from naas_abi_core.services.ServiceBase import ServiceBase


class KeyValueService(ServiceBase):
    __adapter: IKeyValueAdapter

    def __init__(self, adapter: IKeyValueAdapter):
        super().__init__()
        self.__adapter = adapter

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.publish(event)
        except Exception as exc:
            # KV store is the source of truth; event logging must never break it.
            logger.warning(f"KeyValueService: failed to publish event: {exc}")

    def get(self, key: str) -> bytes:
        return self.__adapter.get(key)

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        try:
            result = self.__adapter.set(key, value, ttl)
        except Exception as exc:
            self.__publish_event(
                KeyValueError(key=key, operation="set", message=str(exc))
            )
            raise
        self.__publish_event(
            KeyValueSet(key=key, size_bytes=len(value), ttl_seconds=ttl)
        )
        return result

    def set_if_not_exists(
        self,
        key: str,
        value: bytes,
        ttl: int | None = None,
    ) -> bool:
        try:
            wrote = self.__adapter.set_if_not_exists(key, value, ttl)
        except Exception as exc:
            self.__publish_event(
                KeyValueError(
                    key=key, operation="set_if_not_exists", message=str(exc)
                )
            )
            raise
        if wrote:
            self.__publish_event(
                KeyValueSet(key=key, size_bytes=len(value), ttl_seconds=ttl)
            )
        return wrote

    def delete(self, key: str) -> None:
        try:
            result = self.__adapter.delete(key)
        except Exception as exc:
            self.__publish_event(
                KeyValueError(key=key, operation="delete", message=str(exc))
            )
            raise
        self.__publish_event(KeyValueDeleted(key=key))
        return result

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        try:
            deleted = self.__adapter.delete_if_value_matches(key, value)
        except Exception as exc:
            self.__publish_event(
                KeyValueError(
                    key=key,
                    operation="delete_if_value_matches",
                    message=str(exc),
                )
            )
            raise
        if deleted:
            self.__publish_event(KeyValueDeleted(key=key))
        return deleted

    def exists(self, key: str) -> bool:
        return self.__adapter.exists(key)
