import os
from queue import Queue
import tempfile
import threading
from typing import Optional

from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions,
    IObjectStorageAdapter,
)


class ObjectStorageSecondaryAdapterFS(IObjectStorageAdapter):
    def __init__(self, base_path: str):
        self.base_path = base_path
        self._lock = threading.RLock()
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
        with self._lock:
            self.__path_exists(prefix, key)

            with open(os.path.join(self.base_path, prefix, key), "rb") as f:
                return f.read()

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        with self._lock:
            self.__create_path(prefix)
            target_path = os.path.join(self.base_path, prefix, key)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=os.path.join(self.base_path, prefix),
                delete=False,
            ) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name

            os.replace(temp_path, target_path)

    def delete_object(self, prefix: str, key: str) -> None:
        with self._lock:
            self.__path_exists(prefix, key)

            os.remove(os.path.join(self.base_path, prefix, key))

    def list_objects(self, prefix: str, queue: Optional[Queue] = None) -> list[str]:
        with self._lock:
            self.__path_exists(prefix)
            return [
                os.path.join(prefix, f)
                for f in os.listdir(os.path.join(self.base_path, prefix))
            ]
