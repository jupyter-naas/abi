"""Tool index backed by the engine's ``VectorStoreService``.

Each embedding model gets its own collection, named
``<prefix>__<model hash>__<dimension>``. Encoding the dimension in the name
lets a restarted process recover it without a metadata record, and encoding
the model hash means switching embedding models never mixes vectors: the
previous model's collection is dropped when the index is prepared for a new
one. Stored fingerprints make re-syncs incremental across restarts.

Tool ids (``ns/name@1``) are not valid point ids for every backend (Qdrant
servers accept only UUIDs and integers), so each entry is stored under a
deterministic UUID derived from the tool id, with the tool id kept in the
entry's metadata and read back from there.
"""

from __future__ import annotations

import hashlib
import re
import threading
import uuid
from collections.abc import Sequence

import numpy as np
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IToolIndexPort,
    ToolIndexEntry,
    ToolIndexHit,
)
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService

_FINGERPRINT_KEY = "tool_fingerprint"
_TOOL_ID_KEY = "tool_id"
_POINT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://naas.ai/abi/tool-registry")


def _point_id(tool_id: str) -> str:
    return str(uuid.uuid5(_POINT_NAMESPACE, tool_id))


class VectorStoreToolIndexAdapter(IToolIndexPort):
    def __init__(
        self,
        vector_store: VectorStoreService,
        collection_prefix: str = "abi_tool_registry",
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", collection_prefix):
            raise ValueError(
                f"collection_prefix {collection_prefix!r} may only contain "
                "letters, digits, '_' and '-'."
            )
        self._store = vector_store
        self._prefix = collection_prefix
        self._lock = threading.RLock()
        self._model_hash: str | None = None
        self._collection: str | None = None
        self._dimension: int | None = None

    # ---------------------------------------------------------------- helpers
    def _own_collections(self) -> list[str]:
        marker = f"{self._prefix}__"
        return [c for c in self._store.list_collections() if c.startswith(marker)]

    def _require_prepared(self) -> str:
        if self._model_hash is None:
            raise RuntimeError(
                "VectorStoreToolIndexAdapter.prepare(model_key) must be called first."
            )
        return self._model_hash

    # ------------------------------------------------------------------- port
    def prepare(self, model_key: str) -> None:
        model_hash = hashlib.sha256(model_key.encode("utf-8")).hexdigest()[:16]
        with self._lock:
            self._model_hash = model_hash
            self._collection = None
            self._dimension = None
            current = f"{self._prefix}__{model_hash}__"
            for name in self._own_collections():
                if name.startswith(current) and self._collection is None:
                    self._collection = name
                    self._dimension = int(name.rsplit("__", 1)[1])
                else:
                    # Another embedding model, or a duplicate: never comparable.
                    self._store.delete_collection(name)

    def fingerprints(self, ids: Sequence[str]) -> dict[str, str]:
        with self._lock:
            self._require_prepared()
            if self._collection is None:
                return {}
            found: dict[str, str] = {}
            for id in ids:
                document = self._store.get_document(
                    self._collection, _point_id(id), include_vector=False
                )
                if document is not None and document.metadata:
                    fingerprint = document.metadata.get(_FINGERPRINT_KEY)
                    if isinstance(fingerprint, str):
                        found[id] = fingerprint
            return found

    def upsert(self, entries: Sequence[ToolIndexEntry]) -> None:
        with self._lock:
            model_hash = self._require_prepared()
            if not entries:
                return
            dimensions = {len(entry.vector) for entry in entries}
            if self._dimension is not None:
                dimensions.add(self._dimension)
            if len(dimensions) != 1:
                raise ValueError(
                    f"Tool vectors must share one dimension, got {sorted(dimensions)}."
                )
            dimension = dimensions.pop()
            if self._collection is None:
                self._collection = f"{self._prefix}__{model_hash}__{dimension}"
                self._store.ensure_collection(
                    self._collection, dimension=dimension, distance_metric="cosine"
                )
                self._dimension = dimension
            self._store.add_documents(
                self._collection,
                ids=[_point_id(entry.id) for entry in entries],
                vectors=[
                    np.asarray(entry.vector, dtype=np.float64) for entry in entries
                ],
                metadata=[
                    {
                        **entry.metadata,
                        _FINGERPRINT_KEY: entry.fingerprint,
                        _TOOL_ID_KEY: entry.id,
                    }
                    for entry in entries
                ],
            )

    def delete(self, ids: Sequence[str]) -> None:
        with self._lock:
            self._require_prepared()
            if self._collection is None or not ids:
                return
            self._store.delete_documents(
                self._collection, [_point_id(id) for id in ids]
            )

    def search(self, vector: Sequence[float], limit: int) -> list[ToolIndexHit]:
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        with self._lock:
            self._require_prepared()
            if self._collection is None:
                return []
            results = self._store.search_similar(
                self._collection,
                np.asarray(vector, dtype=np.float64),
                k=limit,
                # The tool id lives in the metadata; the hit id is a point UUID.
                include_metadata=True,
            )
            return [
                ToolIndexHit(id=str(r.metadata[_TOOL_ID_KEY]), score=float(r.score))
                for r in results
                if r.metadata and _TOOL_ID_KEY in r.metadata
            ]

    def size(self) -> int:
        with self._lock:
            if self._collection is None:
                return 0
            return self._store.get_collection_size(self._collection)
