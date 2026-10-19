from collections.abc import Callable, Iterator
from contextlib import contextmanager
from queue import Queue
from typing import BinaryIO

from naas_abi_core import logger
from naas_abi_core.services.iam.enforcement import ResourceGuard
from naas_abi_core.services.iam.names import path_parts
from naas_abi_core.services.object_storage.iam_catalog import (
    CATALOG,
    OBJECT,
    object_parts,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions,
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
    """Objects by prefix and key. Wired into an engine, every operation is
    authorized on ``object/<prefix>/<key>`` (RFC §6.4): an object the caller
    may not see is ``ObjectNotFound``, and listings hold only the objects the
    caller may list."""

    adapter: IObjectStorageAdapter

    def __init__(self, adapter: IObjectStorageAdapter):
        super().__init__()
        self.adapter = adapter
        self._guard = ResourceGuard.of(CATALOG, self)

    @staticmethod
    def __plain(prefix: str, key: str | None = None) -> None:
        """Refuse a prefix or key that is not a plain path (RFC §4.3).

        IAM checks the name ``prefix/key`` as written, a backend opens what the
        path resolves to: ``ws1/../ws2/x`` matches ``ws1/*`` and opens ``ws2/x``,
        ``/etc/passwd`` replaces the base path. So no ``.`` or ``..`` segment,
        no empty segment (one trailing ``/`` on a prefix aside) and no leading
        ``/`` on a key, whoever the caller is.
        """
        for what, value, trailing in (("prefix", prefix, True), ("key", key, False)):
            if not value:
                continue
            if trailing and value.endswith("/"):
                value = value[:-1]
            segments = value.split("/") if value else []
            if any(s in ("", ".", "..") for s in segments):
                raise Exceptions.InvalidObjectPath(
                    f"The object {what} {value!r} is not a plain path"
                )

    def __require(self, action: str, prefix: str, key: str) -> None:
        self.__plain(prefix, key)
        self._guard.require(
            action,
            OBJECT,
            object_parts(prefix, key),
            not_found=lambda: Exceptions.ObjectNotFound(f"{prefix}/{key} not found"),
        )

    def __listed(
        self,
        action: str,
        prefix: str,
        queue: Queue | None,
        listing: Callable[[str, Queue | None], list[str]],
        *,
        folders: bool = False,
    ) -> list[str]:
        """``listing`` filtered to the objects the caller may list (RFC §5.5).

        With ``folders``, an entry the caller may not list as an object is
        still shown when it is a folder holding something it may list, and a
        folder whose contents a Deny hides is not (``__visible_entries``).
        """
        self.__plain(prefix)
        if self._guard.iam is None or self._guard.allows_every(action, OBJECT):
            return listing(prefix, queue)
        prefixes = self._guard.id_prefixes(action, OBJECT)
        if prefixes == []:
            # Nothing can be allowed: the prefix reads as missing.
            raise Exceptions.ObjectNotFound(f"{prefix} not found")
        # The adapter would fill ``queue`` before filtering: fill it after.
        entries = listing(prefix, None)
        allowed = set(
            self._guard.filter(action, OBJECT, entries, lambda path: path_parts(path))
        )
        objects = (
            self.__visible_entries(action, entries, allowed, prefixes)
            if folders
            else [path for path in entries if path in allowed]
        )
        if queue is not None:
            for path in objects:
                queue.put(path)
        return objects

    def __visible_entries(
        self,
        action: str,
        entries: list[str],
        allowed: set[str],
        prefixes: list[str] | None,
    ) -> list[str]:
        """A folder listing's entries the caller may see. A file is shown when
        it may be listed. A folder (``IObjectStorageAdapter.folders``) is shown
        when it may be listed itself, when a name inside it may be
        (``<entry>/_``, so placements of what is inside apply), or when one of
        the caller's allowed prefixes lies under it; but never when a Deny or
        a suspension refuses the folder, or what is inside it as
        ``<entry>/*`` does: a folder whose every name is hidden is hidden too.
        One filter per listing; a folder shown for one reason only is checked
        for a refusal on the other."""

        def inside(path: str) -> list[str]:
            return [*path_parts(path), "_"]

        folders = self.adapter.folders(entries)
        listed_folders = [path for path in entries if path in folders]
        open_inside = set(self._guard.filter(action, OBJECT, listed_folders, inside))
        visible = []
        for path in entries:
            listable = path in allowed
            if path not in folders:
                if listable:
                    visible.append(path)
                continue
            opens = path in open_inside
            folder = path.strip("/") + "/"
            deeper = prefixes is not None and any(
                p.startswith(folder) for p in prefixes
            )
            if not (listable or opens or deeper):
                continue
            if not listable and self._guard.denies(action, OBJECT, path_parts(path)):
                continue
            if not opens and self._guard.denies(action, OBJECT, inside(path)):
                continue
            visible.append(path)
        return visible

    # Function to avoid creating a new folder 'storage' while using FS adapter
    def __remove_storage_prefix(self, prefix: str) -> str:
        # Only the leading one: ``a/storage/b`` is a path of its own.
        return prefix.removeprefix("storage/")

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.emit(event)
        except Exception as exc:  # noqa: BLE001
            # Storage is the source of truth; event logging must never break it.
            logger.warning(f"ObjectStorageService: failed to publish event: {exc}")

    def get_object(self, prefix: str, key: str) -> bytes:
        prefix = self.__remove_storage_prefix(prefix)
        self.__require("GetObject", prefix, key)
        return self.adapter.get_object(prefix, key)

    @contextmanager
    def get_object_stream(self, prefix: str, key: str) -> Iterator[BinaryIO]:
        prefix = self.__remove_storage_prefix(prefix)
        self.__require("GetObjectStream", prefix, key)
        with self.adapter.get_object_stream(prefix, key) as stream:
            yield stream

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        prefix = self.__remove_storage_prefix(prefix)
        self.__require("PutObject", prefix, key)
        self.adapter.put_object(prefix, key, content)
        self.__publish_event(ObjectPut(prefix=prefix, key=key, size_bytes=len(content)))

    def put_object_stream(self, prefix: str, key: str, stream: BinaryIO) -> None:
        prefix = self.__remove_storage_prefix(prefix)
        self.__require("PutObjectStream", prefix, key)
        self.adapter.put_object_stream(prefix, key, stream)
        # Size isn't known up front when streaming; read it back for the event.
        size = 0
        try:
            size = self.adapter.get_object_metadata(prefix, key).file_size_bytes
        except Exception:  # noqa: BLE001,S110
            pass
        self.__publish_event(ObjectPut(prefix=prefix, key=key, size_bytes=size))

    def delete_object(self, prefix: str, key: str) -> None:
        prefix = self.__remove_storage_prefix(prefix)
        self.__require("DeleteObject", prefix, key)
        self.adapter.delete_object(prefix, key)
        self.__publish_event(ObjectDeleted(prefix=prefix, key=key))

    def list_objects(self, prefix: str = "", queue: Queue | None = None) -> list[str]:
        prefix = self.__remove_storage_prefix(prefix)
        if prefix == "/":
            prefix = ""

        return self.__listed(
            "ListObjects", prefix, queue, self.adapter.list_objects, folders=True
        )

    def list_objects_recursive(
        self, prefix: str = "", queue: Queue | None = None
    ) -> list[str]:
        prefix = self.__remove_storage_prefix(prefix)
        if prefix == "/":
            prefix = ""

        return self.__listed(
            "ListObjectsRecursive", prefix, queue, self.adapter.list_objects_recursive
        )

    def get_object_metadata(self, prefix: str, key: str) -> ObjectMetaData:
        prefix = self.__remove_storage_prefix(prefix)
        self.__require("GetObjectMetadata", prefix, key)
        return self.adapter.get_object_metadata(prefix, key)
