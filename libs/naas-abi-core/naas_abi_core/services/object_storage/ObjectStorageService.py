from queue import Queue
from typing import Optional

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    IObjectStorageAdapter,
    IObjectStorageDomain,
    ObjectMetaData,
)
from naas_abi_core.services.object_storage.ontologies.modules.ObjectStorageEventOntology import (
    ObjectDeleted,
    ObjectPut,
)
from naas_abi_core.services.ServiceBase import ServiceBase


class ObjectStorageService(ServiceBase, IObjectStorageDomain):
    adapter: IObjectStorageAdapter

    def __init__(self, adapter: IObjectStorageAdapter):
        super().__init__()
        self.adapter = adapter

    # Function to avoid creating a new folder 'storage' while using FS adapter
    def __remove_storage_prefix(self, prefix: str) -> str:
        if prefix.startswith("storage/"):
            return prefix.replace("storage/", "")
        return prefix

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.publish(event)
        except Exception as exc:
            # Storage is the source of truth; event logging must never break it.
            logger.warning(f"ObjectStorageService: failed to publish event: {exc}")

    def get_object(self, prefix: str, key: str) -> bytes:
        prefix = self.__remove_storage_prefix(prefix)
        return self.adapter.get_object(prefix, key)

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        prefix = self.__remove_storage_prefix(prefix)
        self.adapter.put_object(prefix, key, content)
        self.__publish_event(
            ObjectPut(prefix=prefix, key=key, size_bytes=len(content))
        )

    def delete_object(self, prefix: str, key: str) -> None:
        prefix = self.__remove_storage_prefix(prefix)
        self.adapter.delete_object(prefix, key)
        self.__publish_event(ObjectDeleted(prefix=prefix, key=key))

    def list_objects(
        self, prefix: str = "", queue: Optional[Queue] = None
    ) -> list[str]:
        prefix = self.__remove_storage_prefix(prefix)
        if prefix == "/":
            prefix = ""

        return self.adapter.list_objects(prefix, queue)

    def get_object_metadata(self, prefix: str, key: str) -> ObjectMetaData:
        return self.adapter.get_object_metadata(prefix, key)
