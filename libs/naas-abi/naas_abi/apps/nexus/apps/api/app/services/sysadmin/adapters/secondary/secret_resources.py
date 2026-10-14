"""The engine secret service as a flat list of keys with masked values.

Wraps ``Secret`` (sync; calls run in a worker thread). Existence is checked
against ``list()``: ``get()`` falls back to process environment variables in
the dotenv adapter, which are not secrets. Values never leave this adapter
unless ``read(..., reveal=True)``; neither their size. Writes and removals go
to every configured secret adapter, as ``Secret.set`` / ``Secret.remove`` do.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    Action,
    InvalidResource,
    ResourceCapabilities,
    ResourceContent,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    UnsupportedOperation,
    paginate,
    text_preview,
)

SERVICE = "secret"
ACTIONS: tuple[Action, ...] = ("read", "reveal", "write", "delete")
# Environment-variable style: dotenv files and process environments both accept it.
KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")


class SecretResources:
    service = SERVICE
    capabilities = ResourceCapabilities(browse=True, create=True, reveal=True)

    def __init__(self, secret: Any) -> None:
        self._secret = secret

    @staticmethod
    def _entry(key: str) -> ResourceEntry:
        return ResourceEntry(key, key, "item", ACTIONS)

    def _keys(self) -> dict[str, str | None]:
        return self._secret.list()

    def _value(self, key: str) -> str:
        secrets = self._keys()
        if key not in secrets:
            raise ResourceNotFound(SERVICE, key)
        return secrets[key] or ""

    def _list(self, parent: str, cursor: str | None, limit: int) -> ResourcePage:
        keys = self._keys()
        if parent:
            if parent in keys:
                raise InvalidResource(SERVICE, f"{parent!r} is a secret, not a folder")
            raise ResourceNotFound(SERVICE, parent)
        return paginate("", [self._entry(k) for k in sorted(keys)], cursor, limit)

    def _stat(self, key: str) -> ResourceEntry:
        self._value(key)
        return self._entry(key)

    def _read(self, key: str, reveal: bool) -> ResourceDetail:
        value = self._value(key)
        content = text_preview(value.encode()) if reveal else ResourceContent("masked")
        return ResourceDetail(self._entry(key), content)

    def _write(self, key: str, content: bytes) -> ResourceEntry:
        if not KEY.fullmatch(key):
            raise InvalidResource(SERVICE, f"invalid secret name {key!r}")
        try:
            value = content.decode("utf-8")
        except UnicodeDecodeError:
            raise InvalidResource(SERVICE, "a secret value must be UTF-8 text") from None
        self._secret.set(key, value)
        return self._entry(key)

    def _delete(self, key: str) -> None:
        self._value(key)
        self._secret.remove(key)

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100
    ) -> ResourcePage:
        return await asyncio.to_thread(self._list, parent, cursor, limit)

    async def stat(self, resource_id: str) -> ResourceEntry:
        return await asyncio.to_thread(self._stat, resource_id)

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        return await asyncio.to_thread(self._read, resource_id, reveal)

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        raise UnsupportedOperation(SERVICE, "download")

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        return await asyncio.to_thread(self._write, resource_id, content)

    async def delete(self, resource_id: str) -> None:
        await asyncio.to_thread(self._delete, resource_id)
