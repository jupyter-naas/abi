"""Object storage as a tree: ids are object paths (``docs/a.pdf``), folders are containers.

Wraps the engine's ``ObjectStorageService`` (sync, so calls run in a worker
thread). Adapters disagree on folders: S3 lists them with a trailing ``/``,
the filesystem adapter does not, so an entry without one is classified by its
metadata (a directory's permissions start with ``d``). Only the listed page pays
for that, and nothing is downloaded to classify or stat an entry.
"""

from __future__ import annotations

import asyncio
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    PREVIEW_BYTES,
    Action,
    InvalidResource,
    ResourceCapabilities,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    ResourceTooLarge,
    paginate,
    text_preview,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions

SERVICE = "object_storage"
ITEM_ACTIONS: tuple[Action, ...] = ("read", "download", "write", "delete")


def _split(resource_id: str) -> tuple[str, str]:
    prefix, _, key = resource_id.rpartition("/")
    return prefix, key


def _validate(resource_id: str) -> str:
    parts = resource_id.split("/")
    if (
        not resource_id
        or resource_id.startswith("/")
        or any(p in ("", ".", "..") for p in parts)
        or "\\" in resource_id
        or "\x00" in resource_id
    ):
        raise InvalidResource(SERVICE, f"invalid object path {resource_id!r}")
    return resource_id


class ObjectStorageResources:
    service = SERVICE
    capabilities = ResourceCapabilities(browse=True, create=True)

    def __init__(self, storage: Any) -> None:
        self._storage = storage

    # --- sync helpers, run in a worker thread ---------------------------------------

    def _entry_from_metadata(self, resource_id: str) -> ResourceEntry:
        prefix, key = _split(resource_id)
        try:
            meta = self._storage.get_object_metadata(prefix, key)
        except Exceptions.ObjectNotFound:
            if self._listable(resource_id):
                return ResourceEntry(resource_id, key, "container")
            raise ResourceNotFound(SERVICE, resource_id) from None
        if (meta.permissions or "").startswith("d"):
            return ResourceEntry(resource_id, key, "container")
        attributes = {"media_type": meta.mime_type} if meta.mime_type else {}
        return ResourceEntry(
            resource_id,
            key,
            "item",
            ITEM_ACTIONS,
            size=meta.file_size_bytes,
            modified=meta.modified_time.isoformat() if meta.modified_time else None,
            attributes=attributes,
        )

    def _listable(self, resource_id: str) -> bool:
        try:
            return bool(self._storage.list_objects(f"{resource_id}/"))
        except (Exceptions.ObjectNotFound, NotADirectoryError, OSError):
            return False

    def _stat(self, resource_id: str) -> ResourceEntry:
        if resource_id == "":
            return ResourceEntry("", "", "container")
        return self._entry_from_metadata(_validate(resource_id))

    def _children(self, parent: str) -> list[tuple[str, bool]]:
        """(child id, listed as a folder) under ``parent``, sorted by id."""
        prefix = f"{parent}/" if parent else ""
        try:
            raw = self._storage.list_objects(prefix)
        except NotADirectoryError:
            raise InvalidResource(SERVICE, f"{parent!r} is an object") from None
        except Exceptions.ObjectNotFound:
            if parent and self._stat(parent).kind == "item":
                raise InvalidResource(SERVICE, f"{parent!r} is an object") from None
            raise ResourceNotFound(SERVICE, parent) from None
        children: dict[str, bool] = {}
        for path in raw:
            folder = path.endswith("/")
            name = path[len(prefix) :] if path.startswith(prefix) else path
            name = name.strip("/")
            if name and "/" not in name:
                children[prefix + name] = children.get(prefix + name, False) or folder
        return sorted(children.items())

    def _list(self, parent: str, cursor: str | None, limit: int) -> ResourcePage:
        if parent:
            _validate(parent)
        children = self._children(parent)
        # Page by id first so only the returned entries pay for classification.
        stubs = [ResourceEntry(child, child.rsplit("/", 1)[-1], "item") for child, _ in children]
        page = paginate(parent, stubs, cursor, limit)
        folders = {child for child, folder in children if folder}
        entries = tuple(
            ResourceEntry(e.id, e.name, "container")
            if e.id in folders
            else self._entry_from_metadata(e.id)
            for e in page.entries
        )
        return ResourcePage(parent, entries, page.next_cursor)

    def _item(self, resource_id: str) -> ResourceEntry:
        entry = self._stat(resource_id)
        if entry.kind != "item":
            raise InvalidResource(SERVICE, f"{resource_id!r} is a folder")
        return entry

    def _read(self, resource_id: str) -> ResourceDetail:
        entry = self._item(resource_id)
        prefix, key = _split(resource_id)
        with self._storage.get_object_stream(prefix, key) as stream:
            head = stream.read(PREVIEW_BYTES + 1)
        return ResourceDetail(entry, text_preview(head, entry.size))

    def _download(self, resource_id: str, max_bytes: int) -> bytes:
        entry = self._item(resource_id)
        if entry.size is not None and entry.size > max_bytes:
            raise ResourceTooLarge(SERVICE, resource_id, entry.size, max_bytes)
        data = self._storage.get_object(*_split(resource_id))
        if len(data) > max_bytes:
            raise ResourceTooLarge(SERVICE, resource_id, len(data), max_bytes)
        return data

    def _write(self, resource_id: str, content: bytes) -> ResourceEntry:
        _validate(resource_id)
        try:
            if self._stat(resource_id).kind == "container":
                raise InvalidResource(SERVICE, f"{resource_id!r} is a folder")
        except ResourceNotFound:
            pass
        self._storage.put_object(*_split(resource_id), content)
        return self._stat(resource_id)

    def _delete(self, resource_id: str) -> None:
        self._item(resource_id)
        self._storage.delete_object(*_split(resource_id))

    # --- ServiceResources --------------------------------------------------------------

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100
    ) -> ResourcePage:
        return await asyncio.to_thread(self._list, parent, cursor, limit)

    async def stat(self, resource_id: str) -> ResourceEntry:
        return await asyncio.to_thread(self._stat, resource_id)

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        return await asyncio.to_thread(self._read, resource_id)

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        return await asyncio.to_thread(self._download, resource_id, max_bytes)

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        return await asyncio.to_thread(self._write, resource_id, content)

    async def delete(self, resource_id: str) -> None:
        await asyncio.to_thread(self._delete, resource_id)
