"""Vector collections and their documents as a tree, for the System app.

Wraps the engine's ``VectorStoreService`` (sync; calls run in a worker thread).
Collections are containers (deleting one drops it with its documents) and
documents are items with ids ``<collection>/<document id>``, split on the first
``/``; a collection whose own name contains ``/`` cannot be addressed.

A document is written as a JSON object ``{"vector": [...], "metadata": {...},
"payload": {...}}``. Writing into a collection that does not exist creates it
with the vector's length as dimension and ``distance_metric`` (default
``cosine``). Replacing a document replaces its metadata and payload; without
``"vector"`` the stored vector is kept. Reading shows the dimension and the
first components only; a download carries the whole vector.

Listing costs: a collection page reads each collection's info and one sample
vector (for a sparkline); a document page reads the page's metadata and
payloads, never their vectors. Entries carry a one-line ``summary`` (text-like
payload fields first); a read carries a ``vector`` view.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import numpy as np
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
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

SERVICE = "vector_store"
ITEM_ACTIONS: tuple[Action, ...] = ("read", "download", "write", "delete")
COLLECTION_ACTIONS: tuple[Action, ...] = ("delete",)
VECTOR_HEAD = 8
VIEW_COMPONENTS = 96
SAMPLE_COMPONENTS = 32
SUMMARY_LENGTH = 140
# Payload or metadata fields that usually hold what a vector embeds, best first.
TEXT_FIELDS = (
    "title",
    "name",
    "text",
    "content",
    "page_content",
    "chunk",
    "document",
    "description",
    "label",
    "source",
)
METRICS = ("cosine", "euclidean", "l2", "dot", "l1")
FIELDS = {"vector", "metadata", "payload", "distance_metric"}
WRITE_FORMAT = (
    'JSON object: {"vector": [numbers], "metadata": {...}, "payload": {...}}. '
    'A new collection takes the vector length as dimension and "distance_metric" '
    '(default cosine); without "vector" a replace keeps the stored one.'
)


def _invalid(reason: str) -> InvalidResource:
    return InvalidResource(SERVICE, reason)


def _split(resource_id: str) -> tuple[str, str]:
    """(collection, document id); the document id is empty for a collection."""
    collection, separator, document_id = resource_id.partition("/")
    if not collection or (separator and not document_id):
        raise _invalid(f"invalid id {resource_id!r}: use <collection>/<document id>")
    return collection, document_id


def _clip(text: str, limit: int = SUMMARY_LENGTH) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _summary(payload: dict[str, Any] | None, metadata: dict[str, Any] | None) -> str:
    """One line describing what a vector embeds: text-like fields first, else keys."""
    sources = [s for s in (payload, metadata) if isinstance(s, dict) and s]
    for field in TEXT_FIELDS:
        for source in sources:
            value = source.get(field)
            if isinstance(value, str) and value.strip():
                return _clip(value)
    for source in sources:
        scalars = [f"{k}: {v}" for k, v in source.items() if isinstance(v, (str, int, float, bool))]
        if scalars:
            return _clip(" · ".join(scalars[:3]))
    return ""


def _parse(content: bytes) -> tuple[np.ndarray | None, dict[str, Any], dict[str, Any] | None, str]:
    """(vector or None, metadata, payload, distance metric) from a written value."""
    try:
        body = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise _invalid("a document must be a JSON object") from None
    if not isinstance(body, dict):
        raise _invalid("a document must be a JSON object")
    unknown = sorted(set(body) - FIELDS)
    if unknown:
        raise _invalid(f"unknown fields {unknown}; expected {sorted(FIELDS)}")
    raw_vector = body.get("vector")
    vector = None
    if raw_vector is not None:
        if (
            not isinstance(raw_vector, list)
            or not raw_vector
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in raw_vector)
        ):
            raise _invalid('"vector" must be a non-empty list of numbers')
        vector = np.asarray(raw_vector, dtype=np.float32)
    metadata = body.get("metadata", {})
    if not isinstance(metadata, dict):
        raise _invalid('"metadata" must be a JSON object')
    payload = body.get("payload")
    if payload is not None and not isinstance(payload, dict):
        raise _invalid('"payload" must be a JSON object')
    metric = body.get("distance_metric", "cosine")
    if metric not in METRICS:
        raise _invalid(f'"distance_metric" must be one of {list(METRICS)}')
    return vector, metadata, payload, metric


class VectorStoreResources:
    service = SERVICE
    capabilities = ResourceCapabilities(browse=True, create=True, write_format=WRITE_FORMAT)

    def __init__(self, vectors: Any) -> None:
        self._vectors = vectors

    # --- sync helpers, run in a worker thread ---------------------------------------

    def _has_collection(self, name: str) -> bool:
        return name in self._vectors.list_collections()

    def _require_collection(self, name: str, resource_id: str) -> None:
        if not self._has_collection(name):
            raise ResourceNotFound(SERVICE, resource_id)

    def _sample(self, name: str) -> str:
        """The first components of one stored vector, for a sparkline (empty if none)."""
        try:
            page = self._vectors.list_documents(name, limit=1, include_vectors=True)
        except Exception:  # noqa: BLE001 - a sparkline is decoration; never fail a listing for it
            return ""
        if not page.documents:
            return ""
        vector = np.asarray(page.documents[0].vector, dtype=np.float32)[:SAMPLE_COMPONENTS]
        return ",".join(f"{float(v):.4f}" for v in vector)

    def _collection_entry(self, name: str) -> ResourceEntry:
        info = self._vectors.get_collection_info(name)
        attributes = {"documents": str(info.size)}
        facts = [f"{info.size:,} {'vector' if info.size == 1 else 'vectors'}"]
        if info.dimension is not None:
            attributes["dimension"] = str(info.dimension)
            facts.append(f"{info.dimension}-d")
        if info.distance_metric:
            attributes["distance"] = info.distance_metric
            facts.append(info.distance_metric)
        attributes["summary"] = " · ".join(facts)
        sample = self._sample(name) if info.size else ""
        if sample:
            attributes["sample"] = sample
        return ResourceEntry(name, name, "container", COLLECTION_ACTIONS, attributes=attributes)

    @staticmethod
    def _document_entry(collection: str, document_id: str, document: Any = None) -> ResourceEntry:
        attributes: dict[str, str] = {}
        if document is not None:
            summary = _summary(document.payload, document.metadata)
            if summary:
                attributes["summary"] = summary
            keys = sorted({*(document.payload or {}), *(document.metadata or {})})
            if keys:
                attributes["fields"] = ", ".join(keys[:8])
        return ResourceEntry(
            f"{collection}/{document_id}", document_id, "item", ITEM_ACTIONS, attributes=attributes
        )

    def _document(self, resource_id: str, *, include_vector: bool) -> tuple[str, str, Any]:
        collection, document_id = _split(resource_id)
        if not document_id:
            self._require_collection(collection, resource_id)
            raise _invalid(f"{resource_id!r} is a collection")
        self._require_collection(collection, resource_id)
        document = self._vectors.get_document(
            collection, document_id, include_vector=include_vector
        )
        if document is None:
            raise ResourceNotFound(SERVICE, resource_id)
        return collection, document_id, document

    def _list(self, parent: str, cursor: str | None, limit: int) -> ResourcePage:
        if parent == "":
            names = sorted(self._vectors.list_collections())
            stubs = [ResourceEntry(name, name, "container") for name in names]
            page = paginate("", stubs, cursor, limit)
            entries = tuple(self._collection_entry(e.id) for e in page.entries)
            return ResourcePage("", entries, page.next_cursor)
        collection, document_id = _split(parent)
        if document_id:
            self._document(parent, include_vector=False)
            raise _invalid(f"{parent!r} is a document, not a collection")
        self._require_collection(collection, parent)
        documents = self._vectors.list_documents(collection, limit=limit, cursor=cursor)
        entries = tuple(self._document_entry(collection, d.id, d) for d in documents.documents)
        return ResourcePage(parent, entries, documents.next_cursor)

    def _stat(self, resource_id: str) -> ResourceEntry:
        if resource_id == "":
            return ResourceEntry("", "", "container")
        collection, document_id = _split(resource_id)
        if not document_id:
            self._require_collection(collection, resource_id)
            return self._collection_entry(collection)
        _, _, document = self._document(resource_id, include_vector=False)
        return self._document_entry(collection, document_id, document)

    def _read(self, resource_id: str) -> ResourceDetail:
        collection, document_id, document = self._document(resource_id, include_vector=True)
        array = np.asarray(document.vector, dtype=np.float32)
        vector = array.tolist()
        body = {
            "id": document_id,
            "collection": collection,
            "dimension": len(vector),
            "vector_head": [round(float(v), 6) for v in vector[:VECTOR_HEAD]],
            "metadata": document.metadata or {},
            "payload": document.payload,
        }
        raw = json.dumps(body, indent=2, ensure_ascii=False, default=str).encode()
        view = {
            "type": "vector",
            "dimension": len(vector),
            "components": [round(float(v), 6) for v in vector[:VIEW_COMPONENTS]],
            "norm": round(float(np.linalg.norm(array)), 6) if array.size else None,
            # Round-trip through JSON so numpy or datetime values become plain JSON.
            "metadata": json.loads(json.dumps(document.metadata or {}, default=str)),
            "payload": json.loads(json.dumps(document.payload or {}, default=str)),
        }
        return ResourceDetail(
            self._document_entry(collection, document_id, document), text_preview(raw), view
        )

    def _download(self, resource_id: str, max_bytes: int) -> bytes:
        collection, document_id, document = self._document(resource_id, include_vector=True)
        body = {
            "id": document_id,
            "collection": collection,
            "vector": [float(v) for v in np.asarray(document.vector, dtype=np.float32)],
            "metadata": document.metadata or {},
            "payload": document.payload,
        }
        data = json.dumps(body, ensure_ascii=False, default=str).encode()
        if len(data) > max_bytes:
            raise ResourceTooLarge(SERVICE, resource_id, len(data), max_bytes)
        return data

    def _write(self, resource_id: str, content: bytes) -> ResourceEntry:
        collection, document_id = _split(resource_id)
        if not document_id:
            raise _invalid("write documents as <collection>/<document id>")
        vector, metadata, payload, metric = _parse(content)
        exists = self._has_collection(collection)
        if vector is None:
            existing = (
                self._vectors.get_document(collection, document_id, include_vector=True)
                if exists
                else None
            )
            if existing is None or np.asarray(existing.vector).size == 0:
                raise _invalid('a new document needs a "vector"')
            vector = np.asarray(existing.vector, dtype=np.float32)
        if not exists:
            self._vectors.ensure_collection(
                collection, dimension=int(vector.shape[0]), distance_metric=metric
            )
        else:
            dimension = self._vectors.get_collection_info(collection).dimension
            if dimension is not None and dimension != vector.shape[0]:
                raise _invalid(
                    f"the vector has {vector.shape[0]} components; "
                    f"{collection!r} expects {dimension}"
                )
        self._vectors.add_documents(
            collection,
            [document_id],
            [vector],
            metadata=[metadata],
            payloads=[payload] if payload is not None else None,
        )
        return self._document_entry(collection, document_id)

    def _delete(self, resource_id: str) -> None:
        collection, document_id = _split(resource_id)
        if not document_id:
            self._require_collection(collection, resource_id)
            self._vectors.delete_collection(collection)
            return
        self._document(resource_id, include_vector=False)
        self._vectors.delete_documents(collection, [document_id])

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
