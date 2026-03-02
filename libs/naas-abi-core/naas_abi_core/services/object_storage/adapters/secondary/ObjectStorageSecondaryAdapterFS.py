import os
from queue import Queue
from typing import Optional

from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions,
    IObjectStorageAdapter,
)


class ObjectStorageSecondaryAdapterFS(IObjectStorageAdapter):
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.__create_path(base_path)

    def __create_path(self, prefix: str) -> None:
        os.makedirs(os.path.join(self.base_path, prefix), exist_ok=True)

    def __path_exists(self, prefix: str, key: str | None = None) -> bool:
        if key is None:
            exists = os.path.exists(os.path.join(self.base_path, prefix))
        else:
            exists = os.path.exists(os.path.join(self.base_path, prefix, key))

        if not exists:
            raise Exceptions.ObjectNotFound(f"Object {prefix}/{key} not found")

        return exists

    def get_object(self, prefix: str, key: str) -> bytes:
        self.__path_exists(prefix, key)

        with open(os.path.join(self.base_path, prefix, key), "rb") as f:
            return f.read()

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.__create_path(prefix)

        with open(os.path.join(self.base_path, prefix, key), "wb") as f:
            f.write(content)

    def delete_object(self, prefix: str, key: str) -> None:
        self.__path_exists(prefix, key)

        os.remove(os.path.join(self.base_path, prefix, key))

    def list_objects(self, prefix: str, queue: Optional[Queue] = None) -> list[str]:
        self.__path_exists(prefix)
        return [
            os.path.join(prefix, f)
            for f in os.listdir(os.path.join(self.base_path, prefix))
        ]
