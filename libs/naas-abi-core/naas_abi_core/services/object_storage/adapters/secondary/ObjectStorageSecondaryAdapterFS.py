import os
import stat
import tempfile
import threading
from datetime import datetime
from queue import Queue
import hashlib
import mimetypes
from typing import Any, Dict, Optional

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
            objects = [
                os.path.join(prefix, f)
                for f in os.listdir(os.path.join(self.base_path, prefix))
            ]
            if queue:
                for obj in objects:
                    queue.put(obj)
            return objects

    def get_object_metadata(self, prefix: str, key: str) -> Dict[str, Any]:
        self.__path_exists(prefix, key)

        file_path = os.path.join(self.base_path, prefix, key)
        stat_info = os.stat(file_path)

        mime_type, encoding = mimetypes.guess_type(file_path)

        def compute_hash(path: str, algo: Any) -> str:
            h = algo()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    h.update(chunk)
            return h.hexdigest()

        return {
            "file_path": os.path.abspath(file_path),
            "file_name": os.path.basename(file_path),
            "file_size_bytes": stat_info.st_size,
            "created_time": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
            "modified_time": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            "accessed_time": datetime.fromtimestamp(stat_info.st_atime).isoformat(),
            "is_file": os.path.isfile(file_path),
            "is_directory": os.path.isdir(file_path),
            "permissions": stat.filemode(stat_info.st_mode),
            "mime_type": mime_type,
            "encoding": encoding,
            "md5": compute_hash(file_path, hashlib.md5),
            "sha1": compute_hash(file_path, hashlib.sha1),
            "sha256": compute_hash(file_path, hashlib.sha256),
        }
