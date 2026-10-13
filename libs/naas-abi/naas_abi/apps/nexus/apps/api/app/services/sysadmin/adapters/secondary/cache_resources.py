"""The engine cache as a flat list of keys across its tiers.

Wraps the multi-tier ``CacheService`` (sync; calls run in a worker thread).
Keys come from ``list_keys``, merged across tiers; the cursor is the last key.
Entries are read raw with ``get_entry`` and never deserialized: text and JSON
are previewed as text, while binary and pickle show only their size. A pickle
is never loaded, and its download is the pickle's bytes. Writes store text, or
a binary entry when the bytes are not UTF-8; replacing a JSON entry keeps it
JSON and refuses a value that does not parse. A replace updates every tier that
holds the key; a new key goes where ``CacheService`` writes (the cold tier).

Listed entries carry what the web shows on a row (type, first tier holding the
key, creation time, size, a one-line ``summary`` of text and JSON values). That
costs one raw ``get_entry`` per listed key (100 by default), read hot tier
first. Opening an entry also checks which tiers hold it (one ``exists`` per tier).

Search (``query``) keeps keys containing the text, case-insensitive. Tiers can
only filter by prefix, so a search walks ``list_keys`` pages from the cursor and
stops after ``SEARCH_SCAN`` keys; its cursor is the last key looked at.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
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
    ResourceTooLarge,
    UnsupportedOperation,
    text_preview,
)
from naas_abi_core import logger
from naas_abi_core.services.cache.CachePort import (
    MAX_KEYS_PER_PAGE,
    CacheEntry,
    CacheNotFoundError,
    DataType,
)

SERVICE = "cache"
ACTIONS: tuple[Action, ...] = ("read", "download", "write", "delete")
TEXT_TYPES = (DataType.TEXT, DataType.JSON)
SUMMARY_CHARS = 120
# JSON values up to this size also come back as a structured view.
JSON_VIEW_BYTES = 1 << 20
SEARCH_SCAN = 50_000


def _raw(entry: CacheEntry) -> bytes:
    """The stored value as bytes: text as UTF-8, binary and pickle base64-decoded
    (a pickle stays an opaque byte string)."""
    data = entry.cached.data
    if entry.cached.data_type in TEXT_TYPES:
        return str(data).encode()
    try:
        return base64.b64decode(str(data), validate=True)
    except (binascii.Error, ValueError):
        return str(data).encode()


def _clip(text: str) -> str:
    return text if len(text) <= SUMMARY_CHARS else f"{text[: SUMMARY_CHARS - 1]}…"


def _summary(entry: CacheEntry) -> str:
    """One line of a text or JSON value; nothing for binary and pickle."""
    if entry.cached.data_type not in TEXT_TYPES:
        return ""
    text = str(entry.cached.data)[: SUMMARY_CHARS * 8]
    if entry.cached.data_type == DataType.JSON:
        try:
            parsed = json.loads(str(entry.cached.data))
        except ValueError:
            parsed = None
        if parsed is not None:
            text = json.dumps(parsed, ensure_ascii=False, separators=(", ", ": "))
    return _clip(" ".join(text.split()))


class CacheResources:
    service = SERVICE
    capabilities = ResourceCapabilities(
        browse=True,
        create=True,
        search=True,
        write_format=(
            "Text (stored as a text entry; other bytes as a binary entry). "
            "A JSON entry stays JSON and must parse."
        ),
    )

    def __init__(self, cache: Any) -> None:
        self._cache = cache

    @staticmethod
    def _entry(
        key: str, stored: CacheEntry | None = None, tiers: list[str] | None = None
    ) -> ResourceEntry:
        if stored is None:
            return ResourceEntry(key, key, "item", ACTIONS)
        created = stored.cached.created_at
        attributes = {
            "data_type": stored.cached.data_type.value,
            "tier": stored.tier,
            "created_at": created,
        }
        summary = _summary(stored)
        if summary:
            attributes["summary"] = summary
        if tiers is not None:
            attributes["tiers"] = ", ".join(tiers)
        return ResourceEntry(
            key,
            key,
            "item",
            ACTIONS,
            size=len(_raw(stored)),
            modified=created or None,
            attributes=attributes,
        )

    def _stored(self, key: str) -> CacheEntry:
        try:
            return self._cache.get_entry(key)
        except CacheNotFoundError:
            raise ResourceNotFound(SERVICE, key) from None

    def _row(self, key: str) -> ResourceEntry:
        try:
            return self._entry(key, self._cache.get_entry(key))
        except CacheNotFoundError:
            # Listed by a tier that no longer holds it (expired meanwhile): keep the row.
            return self._entry(key)

    def _keys(self, after: str | None, limit: int) -> Any:
        try:
            return self._cache.list_keys("", limit=limit, after=after)
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
            if self._cache.exists(parent):
                raise InvalidResource(SERVICE, f"{parent!r} is a key, not a folder")
            raise ResourceNotFound(SERVICE, parent)
        if query:
            keys, next_cursor = self._search(query, cursor, limit)
        else:
            page = self._keys(cursor, limit)
            keys, next_cursor = list(page.keys), page.next_after
        return ResourcePage("", tuple(self._row(k) for k in keys), next_cursor)

    def _stat(self, key: str) -> ResourceEntry:
        return self._entry(key, self._stored(key), self._holding_tiers(key))

    def _read(self, key: str) -> ResourceDetail:
        stored = self._stored(key)
        raw = _raw(stored)
        view: dict[str, Any] | None = None
        if stored.cached.data_type in TEXT_TYPES:
            content = text_preview(raw)
            if stored.cached.data_type == DataType.JSON and len(raw) <= JSON_VIEW_BYTES:
                try:
                    view = {"type": "json", "value": json.loads(raw)}
                except ValueError:
                    view = None
        else:
            content = ResourceContent("binary", size=len(raw))
        entry = self._entry(key, stored, self._holding_tiers(key))
        return ResourceDetail(entry, content, view)

    def _download(self, key: str, max_bytes: int) -> bytes:
        raw = _raw(self._stored(key))
        if len(raw) > max_bytes:
            raise ResourceTooLarge(SERVICE, key, len(raw), max_bytes)
        return raw

    def _holding_tiers(self, key: str) -> list[str]:
        holding = []
        for name in self._cache.tier_names:
            try:
                if self._cache.tier(name).exists(key):
                    holding.append(name)
            except Exception as exc:  # noqa: BLE001 - an unreachable tier holds nothing we can update
                logger.warning(f"sysadmin cache: tier {name!r} unavailable: {exc}")
        return holding

    def _write(self, key: str, content: bytes) -> ResourceEntry:
        if not key:
            raise InvalidResource(SERVICE, "a key cannot be empty")
        try:
            text: str | None = content.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        holding = self._holding_tiers(key)
        keep_json = False
        parsed: Any = None
        if holding:
            try:
                keep_json = self._cache.get_entry(key).cached.data_type == DataType.JSON
            except CacheNotFoundError:
                keep_json = False
        if keep_json:
            if text is None:
                raise InvalidResource(SERVICE, "this entry holds JSON; the new value is not text")
            try:
                parsed = json.loads(text)
            except ValueError as exc:
                raise InvalidResource(
                    SERVICE, f"this entry holds JSON; the new value does not parse: {exc}"
                ) from None
        targets = [self._cache.tier(name) for name in holding] or [self._cache]
        for target in targets:
            if keep_json:
                target.set_json(key, parsed)
            elif text is None:
                target.set_binary(key, content)
            else:
                target.set_text(key, text)
        return self._stat(key)

    def _delete(self, key: str) -> None:
        self._stored(key)
        self._cache.delete(key)
        # CacheService.delete swallows per-tier failures: check it really went.
        if self._cache.exists(key):
            raise RuntimeError(f"cache: {key!r} is still held by a tier after delete")

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
