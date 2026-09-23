"""Process-local vector index for tool definitions (numpy cosine similarity).

The default index: tool catalogs hold hundreds to low thousands of entries,
which a brute-force scan handles in well under a millisecond. It is rebuilt on
every boot, like the registry itself.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence

import numpy as np
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IToolIndexPort,
    ToolIndexEntry,
    ToolIndexHit,
)


class InMemoryToolIndexAdapter(IToolIndexPort):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._model_key: str | None = None
        self._dimension: int | None = None
        self._entries: dict[str, tuple[str, np.ndarray]] = {}

    def _require_prepared(self) -> None:
        if self._model_key is None:
            raise RuntimeError(
                "InMemoryToolIndexAdapter.prepare(model_key) must be called first."
            )

    def prepare(self, model_key: str) -> None:
        with self._lock:
            if model_key != self._model_key:
                self._entries.clear()
                self._dimension = None
            self._model_key = model_key

    def fingerprints(self, ids: Sequence[str]) -> dict[str, str]:
        with self._lock:
            self._require_prepared()
            return {id: self._entries[id][0] for id in ids if id in self._entries}

    def upsert(self, entries: Sequence[ToolIndexEntry]) -> None:
        with self._lock:
            self._require_prepared()
            for entry in entries:
                vector = np.asarray(entry.vector, dtype=np.float64)
                if self._dimension is None:
                    self._dimension = int(vector.shape[0])
                elif vector.shape[0] != self._dimension:
                    raise ValueError(
                        f"Vector for '{entry.id}' has dimension {vector.shape[0]}, "
                        f"the index holds dimension {self._dimension}."
                    )
                self._entries[entry.id] = (entry.fingerprint, _normalise(vector))

    def delete(self, ids: Sequence[str]) -> None:
        with self._lock:
            self._require_prepared()
            for id in ids:
                self._entries.pop(id, None)

    def search(self, vector: Sequence[float], limit: int) -> list[ToolIndexHit]:
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        with self._lock:
            self._require_prepared()
            if not self._entries:
                return []
            query = _normalise(np.asarray(vector, dtype=np.float64))
            ids = list(self._entries)
            matrix = np.stack([self._entries[id][1] for id in ids])
            scores = matrix @ query
            ranked = sorted(zip(ids, scores.tolist()), key=lambda p: (-p[1], p[0]))
            return [
                ToolIndexHit(id=id, score=float(score)) for id, score in ranked[:limit]
            ]

    def size(self) -> int:
        with self._lock:
            return len(self._entries)


def _normalise(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 0 else vector
