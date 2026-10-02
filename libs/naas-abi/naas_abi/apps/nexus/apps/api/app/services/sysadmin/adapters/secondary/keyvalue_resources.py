"""The engine key-value store as a flat list of keys with raw byte values.

Wraps ``KeyValueService`` (sync; calls run in a worker thread). Keys come from
``list_keys`` in ascending order and the cursor is the last key listed. Keys may
contain ``/`` but stay flat: there are no containers. Values are raw bytes,
previewed as text when they are UTF-8. Replacing a value keeps the key's
remaining TTL.

Listed entries carry what the web shows on a row: size, ``encoding`` (``json``,
``text`` or ``binary``), a one-line ``summary`` of the value, and the expiry
(``expires_in_seconds`` and an absolute ``expires_at``). That costs one ``get``
and one ``get_ttl`` per listed key (100 by default), which the store answers in
O(1) each.

Search (``query``) keeps keys containing the text, case-insensitive. The store
can only filter by prefix, so a search walks ``list_keys`` pages from the
cursor and stops after ``SEARCH_SCAN`` keys; its cursor is the last key looked
at, so "load more" carries on from there.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    Action,
    InvalidResource,
    ResourceCapabilities,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    ResourceTooLarge,
    UnsupportedOperation,
    text_preview,
)
from naas_abi_core.services.keyvalue.KeyValuePorts import MAX_KEYS_PER_PAGE, KVNotFoundError

SERVICE = "keyvalue"
ACTIONS: tuple[Action, ...] = ("read", "download", "write", "delete")
SUMMARY_CHARS = 120
# Keys examined by one search page before handing a cursor back.
SEARCH_SCAN = 50_000


def describe(value: bytes) -> tuple[str, str]:
    """(encoding, one-line summary) of a stored value, from its first bytes."""
    head = value[: SUMMARY_CHARS * 4]
    try:
        text = head.decode("utf-8")
    except UnicodeDecodeError as exc:
        if len(value) <= len(head) or exc.start < len(head) - 3:
            return "binary", ""
        text = head[: exc.start].decode("utf-8")
    if "\x00" in text:
        return "binary", ""
    stripped = value.strip()
    if stripped[:1] in (b"{", b"[") and len(value) <= 1 << 20:
        try:
            parsed = json.loads(value)
        except (UnicodeDecodeError, ValueError):
            parsed = None
        if isinstance(parsed, (dict, list)):
            return "json", _clip(json.dumps(parsed, ensure_ascii=False, separators=(", ", ": ")))
    return "text", _clip(" ".join(text.split()))


def _clip(text: str) -> str:
    return text if len(text) <= SUMMARY_CHARS else f"{text[: SUMMARY_CHARS - 1]}…"


class KeyValueResources:
    service = SERVICE
    capabilities = ResourceCapabilities(browse=True, create=True, search=True)

    def __init__(self, kv: Any) -> None:
        self._kv = kv

    @staticmethod
    def _entry(key: str, value: bytes | None = None, ttl: int | None = None) -> ResourceEntry:
        attributes: dict[str, str] = {}
        if value is not None:
            encoding, summary = describe(value)
            attributes["encoding"] = encoding
            if summary:
                attributes["summary"] = summary
        if ttl is not None:
            attributes["expires_in_seconds"] = str(ttl)
            attributes["expires_at"] = (datetime.now(UTC) + timedelta(seconds=ttl)).isoformat()
        return ResourceEntry(
            key,
            key,
            "item",
            ACTIONS,
            size=None if value is None else len(value),
            attributes=attributes,
        )

    def _value(self, key: str) -> bytes:
        try:
            return self._kv.get(key)
        except KVNotFoundError:
            raise ResourceNotFound(SERVICE, key) from None

    def _ttl(self, key: str) -> int | None:
        try:
            return self._kv.get_ttl(key)
        except KVNotFoundError:
            raise ResourceNotFound(SERVICE, key) from None

    def _row(self, key: str) -> ResourceEntry | None:
        """A listed key with its value facts; ``None`` when it expired meanwhile."""
        try:
            return self._entry(key, self._kv.get(key), self._kv.get_ttl(key))
        except KVNotFoundError:
            return None

    def _keys(self, after: str | None, limit: int) -> Any:
        try:
            return self._kv.list_keys("", limit=limit, after=after)
        except ValueError as exc:
            raise InvalidResource(SERVICE, str(exc)) from exc
        except NotImplementedError:
            raise UnsupportedOperation(SERVICE, "list") from None

    def _search(self, query: str, cursor: str | None, limit: int) -> tuple[list[str], str | None]:
        needle = query.lower()
        found: list[str] = []
        after, scanned = cursor, 0
        while True:
            page = self._keys(after, MAX_KEYS_PER_PAGE)
            for key in page.keys:
                scanned += 1
                if needle in key.lower():
                    found.append(key)
                    if len(found) == limit:
                        return found, key
            if page.next_after is None:
                return found, None
            after = page.next_after
            if scanned >= SEARCH_SCAN:
                return found, after

    def _list(self, parent: str, cursor: str | None, limit: int, query: str | None) -> ResourcePage:
        if parent:
            if self._kv.exists(parent):
                raise InvalidResource(SERVICE, f"{parent!r} is a key, not a folder")
            raise ResourceNotFound(SERVICE, parent)
        if query:
            keys, next_cursor = self._search(query, cursor, limit)
        else:
            page = self._keys(cursor, limit)
            keys, next_cursor = list(page.keys), page.next_after
        rows = [row for row in (self._row(k) for k in keys) if row is not None]
        return ResourcePage("", tuple(rows), next_cursor)

    def _stat(self, key: str) -> ResourceEntry:
        value = self._value(key)
        return self._entry(key, value, self._ttl(key))

    def _read(self, key: str) -> ResourceDetail:
        value = self._value(key)
        return ResourceDetail(self._entry(key, value, self._ttl(key)), text_preview(value))

    def _download(self, key: str, max_bytes: int) -> bytes:
        value = self._value(key)
        if len(value) > max_bytes:
            raise ResourceTooLarge(SERVICE, key, len(value), max_bytes)
        return value

    def _write(self, key: str, content: bytes) -> ResourceEntry:
        if not key:
            raise InvalidResource(SERVICE, "a key cannot be empty")
        try:
            ttl = self._kv.get_ttl(key)
        except KVNotFoundError:
            ttl = None
        self._kv.set(key, content, ttl)
        return self._stat(key)

    def _delete(self, key: str) -> None:
        try:
            self._kv.delete(key)
        except KVNotFoundError:
            raise ResourceNotFound(SERVICE, key) from None

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100, **options: Any
    ) -> ResourcePage:
        query = options.get("query") or None
        return await asyncio.to_thread(self._list, parent, cursor, limit, query)

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
