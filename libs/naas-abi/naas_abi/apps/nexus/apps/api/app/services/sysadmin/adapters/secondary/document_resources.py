"""The document service across module namespaces, for platform administration.

Wraps the engine's document root (``services.document_admin`` on the unlocked
engine proxy): ``namespaces()`` and ``for_namespace(ns)``. Calls are sync, so
they run in a worker thread. The tree is namespace (container) → collection
(container; delete drops it) → document (item). Ids are
``<namespace>/<collection>/<document id>``. Namespace and collection segments are
percent-quoted, and the document id is the remainder, so it may contain ``/``.

Values use the service's tagged JSON (``document_codec``): datetimes and bytes
are ``{"$t": "datetime" | "bytes", "$v": ...}`` and user keys starting with ``$``
are escaped. What a read shows can be written back unchanged.

Listing costs: a namespace page lists each namespace's collections (one query
per namespace), a collection page counts each collection (one ``COUNT`` per
collection), and a document page reads nothing beyond the page itself. Document
entries carry a one-line ``summary`` and ``fields``: their top-level scalar
values as compact JSON, so the web can show them as table columns.

LangGraph checkpoint collections (``langgraph_checkpoints.py``, schema 2 and 1)
list newest first, grouped by thread, with the step and last message decoded; a
checkpoint reads as a ``checkpoint`` view (its conversation, state, pending
writes and a link to the previous step), and a write's value is decoded.
Decoding never imports. Schema 2 values live in other documents: a listing page
reads each conversation's tail (three batched queries), a checkpoint view reads
its values in batches within the saver's read budget, and at most ``VIEW_PARTS``
bytes of split values. The blob, item and part collections list plainly.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any
from urllib.parse import quote, unquote

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.langgraph_checkpoints import (
    CHECKPOINT_COLLECTIONS,
    CHECKPOINTS,
    LEGACY_CHECKPOINTS,
    LEGACY_WRITES,
    WRITE_COLLECTIONS,
    WRITES,
    checkpoint_attributes,
    checkpoint_view,
    document_key,
    stored_value,
    tail_references,
    write_attributes,
)
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
    UnsupportedOperation,
    paginate,
    text_preview,
)
from naas_abi_core.services.document.adapters.secondary.document_codec import (
    decode,
    encode,
)
from naas_abi_core.services.document.DocumentPort import (
    CollectionNotFound,
    Document,
    DocumentNotFound,
    UniqueViolation,
    VersionConflict,
)
from naas_abi_sdk.langgraph_documents import PARTS, batches, collection_of, references

SERVICE = "document"
SUMMARY_FIELDS = 3
SUMMARY_VALUE = 48
COLUMN_FIELDS = 12
COLUMN_VALUE = 80
# A structured view is the whole document; past this the preview stays text.
VIEW_LIMIT = 512 * 1024
# Fields a summary shows first, when present.
PREFERRED = (
    "title",
    "name",
    "label",
    "status",
    "state",
    "type",
    "kind",
    "email",
    "agent",
    "module",
    "thread_id",
)
DOCUMENT_ACTIONS: tuple[Action, ...] = ("read", "download", "write", "delete")
# Pending writes shown with one checkpoint.
CHECKPOINT_WRITES = 200
# Bytes of split values a checkpoint view reads; messages show 20,000 characters.
VIEW_PARTS = 8 * 1024 * 1024
COLLECTION_ACTIONS: tuple[Action, ...] = ("delete",)


def _segment(name: str) -> str:
    return quote(name, safe="")


def _split(resource_id: str) -> tuple[str, str | None, str | None]:
    """(namespace, collection, document id); missing levels are None."""
    if not resource_id:
        return "", None, None
    parts = resource_id.split("/", 2)
    namespace = unquote(parts[0])
    collection = unquote(parts[1]) if len(parts) > 1 else None
    document = parts[2] if len(parts) > 2 else None
    if not namespace or collection == "" or document == "":
        raise InvalidResource(SERVICE, f"invalid document path {resource_id!r}")
    return namespace, collection, document


def _render(document: Document) -> bytes:
    return json.dumps(encode(document.data), indent=2, ensure_ascii=False).encode()


def _scalar(value: Any, limit: int) -> str | int | float | bool | None:
    """A top-level value as one short cell: scalars as-is, the rest described."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if isinstance(value, dict):
        return f"{{{len(value)} keys}}"
    if isinstance(value, list):
        return f"[{len(value)} items]"
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _summary(data: dict[str, Any]) -> str:
    """The most telling fields first (names, titles, states), then other scalars.

    Storage does not keep key order, so order by meaning, not by position.
    """
    if not data:
        return "empty document"

    def rank(key: str) -> int:
        lowered = key.lower()
        return PREFERRED.index(lowered) if lowered in PREFERRED else len(PREFERRED)

    scalars = [
        (k, v)
        for k, v in data.items()
        if isinstance(v, (str, int, float, bool, datetime)) and v != ""
    ]
    chosen = sorted(scalars, key=lambda kv: rank(kv[0]))[:SUMMARY_FIELDS]
    if not chosen:
        chosen = list(data.items())[:SUMMARY_FIELDS]
    return " · ".join(f"{k}: {_scalar(v, SUMMARY_VALUE)}" for k, v in chosen)


def _fields(data: dict[str, Any]) -> str:
    """Top-level values as compact JSON (the web derives table columns from them)."""
    return json.dumps(
        {k: _scalar(v, COLUMN_VALUE) for k, v in list(data.items())[:COLUMN_FIELDS]},
        ensure_ascii=False,
        default=str,
    )


def _count(value: int, one: str, many: str) -> str:
    return f"{value:,} {one if value == 1 else many}"


def _langgraph_attributes(
    collection: str, data: dict[str, Any], fetched: dict[str, Any] | None = None
) -> dict[str, str]:
    """Decoded listing attributes for checkpoint collections; nothing elsewhere."""
    try:
        if collection in CHECKPOINT_COLLECTIONS:
            return checkpoint_attributes(data, fetched)
        if collection in WRITE_COLLECTIONS:
            return write_attributes(data)
    except Exception:  # noqa: BLE001 - an unreadable checkpoint still lists
        return {}
    return {}


def _by_thread(documents: list[Document]) -> list[Document]:
    """Threads in order of their newest checkpoint, each thread's documents together."""
    order: dict[Any, int] = {}
    for document in documents:
        order.setdefault(document.data.get("thread_id"), len(order))
    return sorted(documents, key=lambda d: order[d.data.get("thread_id")])


class DocumentResources:
    service = SERVICE
    capabilities = ResourceCapabilities(
        browse=True,
        create=True,
        write_format=(
            'JSON object. Dates and bytes are tagged: {"$t": "datetime", "$v": "2026-10-02T08:00:00+00:00"}, '
            '{"$t": "bytes", "$v": "<base64>"}.'
        ),
    )

    def __init__(self, root: Any) -> None:
        # The engine's document root: namespaces() and for_namespace(namespace).
        self._root = root

    # --- entries ---------------------------------------------------------------------

    def _namespace_entry(self, namespace: str) -> ResourceEntry:
        collections = len(self._root.for_namespace(namespace).collections())
        return ResourceEntry(
            _segment(namespace),
            namespace,
            "container",
            attributes={
                "collections": str(collections),
                "summary": _count(collections, "collection", "collections"),
            },
        )

    def _collection_entry(self, namespace: str, collection: str) -> ResourceEntry:
        documents = self._root.for_namespace(namespace).count(collection)
        return ResourceEntry(
            f"{_segment(namespace)}/{_segment(collection)}",
            collection,
            "container",
            COLLECTION_ACTIONS,
            attributes={
                "documents": str(documents),
                "summary": _count(documents, "document", "documents"),
            },
        )

    def _document_entry(
        self,
        namespace: str,
        collection: str,
        document: Document,
        fetched: dict[str, Any] | None = None,
    ) -> ResourceEntry:
        return ResourceEntry(
            f"{_segment(namespace)}/{_segment(collection)}/{document.id}",
            document.id,
            "item",
            DOCUMENT_ACTIONS,
            modified=document.updated_at.isoformat(),
            attributes={
                "version": str(document.version),
                "created_at": document.created_at.isoformat(),
                "keys": str(len(document.data)),
                "summary": _summary(document.data),
                "fields": _fields(document.data),
            }
            | _langgraph_attributes(collection, document.data, fetched),
        )

    # --- lookups ---------------------------------------------------------------------

    def _require_namespace(self, namespace: str, resource_id: str) -> Any:
        if namespace not in self._root.namespaces():
            raise ResourceNotFound(SERVICE, resource_id)
        return self._root.for_namespace(namespace)

    def _require_collection(self, namespace: str, collection: str, resource_id: str) -> Any:
        view = self._require_namespace(namespace, resource_id)
        if collection not in view.collections():
            raise ResourceNotFound(SERVICE, resource_id)
        return view

    def _document(self, resource_id: str) -> tuple[str, str, Document]:
        namespace, collection, document_id = _split(resource_id)
        if collection is None or document_id is None:
            raise InvalidResource(SERVICE, f"{resource_id!r} is not a document")
        try:
            document = self._root.for_namespace(namespace).get(collection, document_id)
        except (DocumentNotFound, CollectionNotFound):
            raise ResourceNotFound(SERVICE, resource_id) from None
        except ValueError as exc:
            raise InvalidResource(SERVICE, str(exc)) from None
        return namespace, collection, document

    # --- LangGraph schema 2 values -----------------------------------------------------

    def _fetch(
        self, view: Any, data: dict[str, Any], wanted: list[tuple[str, int]]
    ) -> list[dict[str, Any]]:
        """Documents by ref in the thread of ``data``, in read-budget batches."""
        scope = [
            ("agent_id", "eq", data.get("agent_id")),
            ("thread_id", "eq", data.get("thread_id")),
        ]
        found: list[dict[str, Any]] = []
        for collection, refs in batches(wanted):
            try:
                # Every page: one can be cut short by the engine's byte budget.
                documents = view.iterate(
                    collection, where=[*scope, ("ref", "in", refs)], batch=len(refs)
                )
                found.extend(d.data for d in documents)
            except (CollectionNotFound, ValueError):
                continue
        return found

    def _values(self, view: Any, roots: list[dict[str, Any]]) -> dict[str, Any]:
        """What schema 2 ``roots`` reference, all levels, at most VIEW_PARTS of parts."""
        fetched: dict[str, Any] = {}
        pending = [r for d in roots for r in references(d)]
        parts = 0
        while pending:
            wanted = []
            for ref, size in dict(pending).items():
                if ref in fetched:
                    continue
                if collection_of(ref) == PARTS:
                    if parts + size > VIEW_PARTS:
                        continue
                    parts += size
                wanted.append((ref, size))
            found = self._fetch(view, roots[0], wanted) if wanted else []
            fetched.update((d["ref"], d) for d in found)
            pending = [r for d in found for r in references(d)]
        return fetched

    def _tails(self, view: Any, documents: list[Document]) -> dict[str, Any]:
        """Each listed conversation's message count and last message (schema 2)."""
        fetched: dict[str, Any] = {}
        for _ in range(3):  # blob, last chunk, last element
            by_thread: dict[tuple[Any, Any], list[tuple[str, int]]] = {}
            for document in documents:
                data = document.data
                for ref in tail_references(data, fetched):
                    by_thread.setdefault((data.get("agent_id"), data.get("thread_id")), []).append(
                        ref
                    )
            if not by_thread:
                break
            for (agent_id, thread_id), wanted in by_thread.items():
                scope = {"agent_id": agent_id, "thread_id": thread_id}
                fetched.update((d["ref"], d) for d in self._fetch(view, scope, wanted))
        return fetched

    # --- sync operations, run in a worker thread --------------------------------------

    def _list(self, parent: str, cursor: str | None, limit: int) -> ResourcePage:
        namespace, collection, document_id = _split(parent)
        if not namespace:
            # Page by name first so only the returned namespaces pay for their counts.
            stubs = [ResourceEntry(_segment(n), n, "container") for n in self._root.namespaces()]
            page = paginate("", stubs, cursor, limit)
            entries = tuple(self._namespace_entry(e.name) for e in page.entries)
            return ResourcePage("", entries, page.next_cursor)
        if collection is None:
            view = self._require_namespace(namespace, parent)
            stubs = [ResourceEntry(c, c, "container") for c in sorted(view.collections())]
            page = paginate(parent, stubs, cursor, limit)
            entries = tuple(self._collection_entry(namespace, e.name) for e in page.entries)
            return ResourcePage(parent, entries, page.next_cursor)
        if document_id is not None:
            self._document(parent)
            raise InvalidResource(SERVICE, f"{parent!r} is a document")
        view = self._root.for_namespace(namespace)
        checkpoints = collection in CHECKPOINT_COLLECTIONS + WRITE_COLLECTIONS
        try:
            if checkpoints:
                try:
                    page = view.find(
                        collection, order_by=("checkpoint_id", "desc"), limit=limit, cursor=cursor
                    )
                except ValueError:  # an older collection without the field declared
                    page = view.find(collection, limit=limit, cursor=cursor)
            else:
                page = view.find(collection, limit=limit, cursor=cursor)
        except CollectionNotFound:
            raise ResourceNotFound(SERVICE, parent) from None
        except ValueError as exc:
            raise InvalidResource(SERVICE, str(exc)) from None
        items = _by_thread(page.items) if checkpoints else page.items
        fetched = self._tails(view, items) if collection == CHECKPOINTS else None
        return ResourcePage(
            parent,
            tuple(self._document_entry(namespace, collection, d, fetched) for d in items),
            page.cursor,
        )

    def _stat(self, resource_id: str) -> ResourceEntry:
        namespace, collection, document_id = _split(resource_id)
        if not namespace:
            return ResourceEntry("", "", "container")
        if collection is None:
            self._require_namespace(namespace, resource_id)
            return self._namespace_entry(namespace)
        if document_id is None:
            self._require_collection(namespace, collection, resource_id)
            return self._collection_entry(namespace, collection)
        namespace, collection, document = self._document(resource_id)
        return self._document_entry(namespace, collection, document)

    def _checkpoint_view(
        self, namespace: str, collection: str, document: Document
    ) -> dict[str, Any] | None:
        data = document.data
        legacy = collection == LEGACY_CHECKPOINTS
        scope = [data.get(k) for k in ("agent_id", "thread_id", "checkpoint_ns", "checkpoint_id")]
        view = self._root.for_namespace(namespace)
        try:
            writes = view.find(
                LEGACY_WRITES if legacy else WRITES,
                where=[
                    (k, "eq", v)
                    for k, v in zip(
                        ("agent_id", "thread_id", "checkpoint_ns", "checkpoint_id"),
                        scope,
                        strict=True,
                    )
                ],
                limit=CHECKPOINT_WRITES,
            ).items
        except (CollectionNotFound, ValueError):
            writes = []
        parent = None
        if data.get("parent_id") and data.get("agent_id"):
            key = document_key(
                str(data["agent_id"]),
                data.get("thread_id"),
                data.get("checkpoint_ns"),
                data["parent_id"],
            )
            # A thread continued from schema 1 has a schema 1 parent.
            home = collection if legacy or view.exists(collection, key) else LEGACY_CHECKPOINTS
            parent = f"{_segment(namespace)}/{_segment(home)}/{key}"
        ordered = sorted(
            (w.data for w in writes), key=lambda w: (str(w.get("task_id")), w.get("index") or 0)
        )
        try:
            fetched = {} if legacy else self._values(view, [data, *ordered])
            shown = checkpoint_view(data, ordered, parent, fetched)
        except Exception:  # noqa: BLE001 - fall back to the raw document
            return None
        return (
            shown if len(json.dumps(shown, ensure_ascii=False, default=str)) <= VIEW_LIMIT else None
        )

    def _read(self, resource_id: str) -> ResourceDetail:
        namespace, collection, document = self._document(resource_id)
        body = _render(document)
        view: dict[str, Any] | None = None
        if collection in CHECKPOINT_COLLECTIONS:
            view = self._checkpoint_view(namespace, collection, document)
        elif collection in WRITE_COLLECTIONS and "value" in document.data:
            namespace_view = self._root.for_namespace(namespace)
            fetched = self._values(namespace_view, [document.data])
            decoded = stored_value(document.data["value"], fetched)
            view = {"type": "json", "value": encode(document.data) | {"value": decoded}}
        if view is None and len(body) <= VIEW_LIMIT:
            view = {"type": "json", "value": encode(document.data)}
        return ResourceDetail(
            self._document_entry(namespace, collection, document),
            text_preview(body[: PREVIEW_BYTES + 1], len(body)),
            view,
        )

    def _download(self, resource_id: str, max_bytes: int) -> bytes:
        _, _, document = self._document(resource_id)
        body = _render(document)
        if len(body) > max_bytes:
            raise ResourceTooLarge(SERVICE, resource_id, len(body), max_bytes)
        return body

    def _write(self, resource_id: str, content: bytes) -> ResourceEntry:
        namespace, collection, document_id = _split(resource_id)
        if collection is None or document_id is None:
            raise InvalidResource(SERVICE, "only documents can be written")
        try:
            data = decode(json.loads(content))
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidResource(SERVICE, f"not valid tagged JSON: {exc}") from None
        if not isinstance(data, dict):
            raise InvalidResource(SERVICE, "a document must be a JSON object")
        try:
            self._root.for_namespace(namespace).put(collection, document_id, data)
        except CollectionNotFound:
            raise InvalidResource(
                SERVICE, f"collection {collection!r} does not exist in {namespace!r}"
            ) from None
        except UniqueViolation as exc:
            raise InvalidResource(SERVICE, f"unique constraint: {exc}") from None
        except ValueError as exc:
            raise InvalidResource(SERVICE, str(exc)) from None
        return self._stat(resource_id)

    def _delete(self, resource_id: str) -> None:
        namespace, collection, document_id = _split(resource_id)
        if not namespace:
            raise InvalidResource(SERVICE, "the root cannot be deleted")
        if collection is None:
            self._require_namespace(namespace, resource_id)
            raise UnsupportedOperation(SERVICE, "delete a namespace")
        if document_id is None:
            view = self._require_collection(namespace, collection, resource_id)
            view.drop_collection(collection)
            return
        namespace, collection, document = self._document(resource_id)
        try:
            # Delete what was just read; a concurrent change is reported, not overwritten.
            self._root.for_namespace(namespace).delete(
                collection, document.id, if_version=document.version
            )
        except VersionConflict:
            raise InvalidResource(SERVICE, f"{resource_id!r} changed meanwhile; retry") from None

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
