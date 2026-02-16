from queue import Queue
from typing import Optional

from naas_abi_core.services.object_storage.ObjectStoragePort import (
    IObjectStorageAdapter,
    IObjectStorageDomain,
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

    def get_object(self, prefix: str, key: str) -> bytes:
        prefix = self.__remove_storage_prefix(prefix)
        return self.adapter.get_object(prefix, key)

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        prefix = self.__remove_storage_prefix(prefix)
        self.adapter.put_object(prefix, key, content)

    def delete_object(self, prefix: str, key: str) -> None:
        prefix = self.__remove_storage_prefix(prefix)
        self.adapter.delete_object(prefix, key)

    def list_objects(
        self, prefix: str = "", queue: Optional[Queue] = None
    ) -> list[str]:
        prefix = self.__remove_storage_prefix(prefix)
        if prefix == "/":
            prefix = ""

        return self.adapter.list_objects(prefix, queue)
