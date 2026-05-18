"""
SQLite + sqlite-vec backed vector store.

This adapter exists for the no-docker dev runtime: the local Qdrant client
holds an exclusive lock on its storage directory, so api and dagster can't
both open the same on-disk store. SQLite with WAL gives concurrent readers
plus serialized writers across processes — exactly what we need — and the
``sqlite-vec`` extension supplies the vector distance functions.

Tradeoffs vs Qdrant:
  * Flat scan via ``vec_distance_<metric>``. Fine for dev datasets
    (<100k vectors); for larger sets we'd switch to a ``vec0`` virtual
    table. Not implemented here.
  * Filter DSL is restricted to single-field equality on metadata via
    ``json_extract`` — enough for the common case used in dev pipelines.
  * Behavior is intentionally a subset of the Qdrant adapter so it can be
    swapped at config time without code changes.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

import numpy as np

from ..IVectorStorePort import IVectorStorePort, SearchResult, VectorDocument

logger = logging.getLogger(__name__)


_SUPPORTED_METRICS = {"cosine", "euclidean", "l2", "dot", "l1"}


def _metric_function(metric: str) -> str:
    """Return the sqlite-vec function name for the given distance metric."""
    m = metric.lower()
    if m in ("cosine",):
        return "vec_distance_cosine"
    if m in ("euclidean", "l2"):
        return "vec_distance_L2"
    if m in ("l1",):
        return "vec_distance_L1"
    if m in ("dot",):
        # sqlite-vec doesn't ship a dot product directly; emulate as
        # negative cosine for ordering (works for top-k where we don't care
        # about absolute magnitude). Keeping behavior explicit for callers.
        return "vec_distance_cosine"
    raise ValueError(
        f"Unsupported distance_metric: {metric!r}. "
        f"Supported: {sorted(_SUPPORTED_METRICS)}"
    )


def _pack_vector(vec: np.ndarray) -> bytes:
    """Encode an ndarray as a contiguous float32 byte string for sqlite-vec."""
    arr = np.ascontiguousarray(np.asarray(vec, dtype=np.float32))
    return arr.tobytes()


def _unpack_vector(blob: bytes, dimension: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32, count=dimension).copy()


class SqliteVecAdapter(IVectorStorePort):
    """File-backed vector store using SQLite WAL + sqlite-vec."""

    def __init__(
        self,
        persistence_path: str,
        journal_mode: str = "WAL",
        busy_timeout_ms: int = 5000,
    ) -> None:
        self.persistence_path = persistence_path
        self.journal_mode = journal_mode
        self.busy_timeout_ms = busy_timeout_ms
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        with self._lock:
            if self._conn is not None:
                return

            os.makedirs(
                os.path.dirname(self.persistence_path) or ".", exist_ok=True
            )

            # Local import: sqlite_vec is a native dep, only pulled in when
            # the adapter is actually instantiated.
            import sqlite_vec  # type: ignore[import-not-found]

            conn = sqlite3.connect(
                self.persistence_path,
                timeout=max(0.0, self.busy_timeout_ms / 1000),
                check_same_thread=False,
                isolation_level=None,  # autocommit; we manage transactions
            )
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
            conn.execute(f"PRAGMA journal_mode={self.journal_mode}")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")

            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)

            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS collections (
                    name TEXT PRIMARY KEY,
                    dimension INTEGER NOT NULL,
                    distance_metric TEXT NOT NULL DEFAULT 'cosine'
                );
                CREATE TABLE IF NOT EXISTS vectors (
                    collection TEXT NOT NULL
                        REFERENCES collections(name) ON DELETE CASCADE,
                    id TEXT NOT NULL,
                    vector BLOB NOT NULL,
                    metadata TEXT,
                    payload TEXT,
                    PRIMARY KEY (collection, id)
                );
                CREATE INDEX IF NOT EXISTS idx_vectors_collection
                    ON vectors(collection);
                """
            )

            self._conn = conn
            logger.info(
                "SqliteVecAdapter initialized at %s (WAL, busy_timeout=%dms)",
                self.persistence_path,
                self.busy_timeout_ms,
            )

    def _require(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Adapter not initialized")
        return self._conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------

    def create_collection(
        self,
        collection_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs: Any,
    ) -> None:
        # Validate metric early so callers see ValueError, not opaque
        # SQLite syntax errors later at search time.
        _metric_function(distance_metric)
        if dimension <= 0:
            raise ValueError("dimension must be a positive integer")
        with self._lock:
            conn = self._require()
            conn.execute(
                "INSERT OR REPLACE INTO collections(name, dimension, distance_metric)"
                " VALUES(?, ?, ?)",
                (collection_name, dimension, distance_metric.lower()),
            )

    def delete_collection(self, collection_name: str) -> None:
        with self._lock:
            conn = self._require()
            # FK ON DELETE CASCADE removes the vectors rows.
            conn.execute("DELETE FROM collections WHERE name = ?", (collection_name,))

    def list_collections(self) -> List[str]:
        with self._lock:
            conn = self._require()
            return [
                row[0]
                for row in conn.execute("SELECT name FROM collections ORDER BY name")
            ]

    def _collection_info(self, name: str) -> tuple[int, str]:
        conn = self._require()
        row = conn.execute(
            "SELECT dimension, distance_metric FROM collections WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Collection not found: {name}")
        return row[0], row[1]

    # ------------------------------------------------------------------
    # Vectors
    # ------------------------------------------------------------------

    def store_vectors(
        self,
        collection_name: str,
        documents: List[VectorDocument],
    ) -> None:
        if not documents:
            return
        with self._lock:
            conn = self._require()
            dim, _ = self._collection_info(collection_name)
            rows = []
            for doc in documents:
                vec = np.asarray(doc.vector, dtype=np.float32)
                if vec.shape != (dim,):
                    raise ValueError(
                        f"vector dimension mismatch for id={doc.id}: "
                        f"expected {dim}, got {vec.shape}"
                    )
                rows.append(
                    (
                        collection_name,
                        doc.id,
                        _pack_vector(vec),
                        json.dumps(doc.metadata) if doc.metadata else None,
                        json.dumps(doc.payload) if doc.payload else None,
                    )
                )
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.executemany(
                    "INSERT OR REPLACE INTO vectors"
                    "(collection, id, vector, metadata, payload)"
                    " VALUES(?, ?, ?, ?, ?)",
                    rows,
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def _build_filter_sql(
        self, filter_spec: Optional[Dict[str, Any]]
    ) -> tuple[str, list[Any]]:
        """Translate a flat equality filter into SQL.

        Only single-field equality (`{key: value}`) is supported. Anything
        more complex raises NotImplementedError — keeps the failure visible
        instead of silently ignoring conditions.
        """
        if not filter_spec:
            return "", []
        clauses: list[str] = []
        params: list[Any] = []
        for key, value in filter_spec.items():
            if isinstance(value, (dict, list)):
                raise NotImplementedError(
                    f"SqliteVecAdapter only supports simple equality filters; "
                    f"got nested value for key {key!r}"
                )
            clauses.append(
                "json_extract(metadata, '$.' || ?) = ?"
            )
            params.extend([key, value])
        return " AND " + " AND ".join(clauses), params

    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_vectors: bool = False,
        include_metadata: bool = True,
    ) -> List[SearchResult]:
        with self._lock:
            conn = self._require()
            dim, metric = self._collection_info(collection_name)
            distance_fn = _metric_function(metric)
            filter_sql, filter_params = self._build_filter_sql(filter)
            sql = (
                f"SELECT id, vector, metadata, payload, "
                f"  {distance_fn}(vector, ?) AS distance "
                f"FROM vectors "
                f"WHERE collection = ?{filter_sql} "
                f"ORDER BY distance ASC LIMIT ?"
            )
            qbytes = _pack_vector(np.asarray(query_vector, dtype=np.float32))
            params = [qbytes, collection_name, *filter_params, k]
            rows = conn.execute(sql, params).fetchall()

            results: List[SearchResult] = []
            for row in rows:
                metadata = (
                    json.loads(row["metadata"])
                    if include_metadata and row["metadata"]
                    else None
                )
                payload = json.loads(row["payload"]) if row["payload"] else None
                vec = (
                    _unpack_vector(row["vector"], dim) if include_vectors else None
                )
                results.append(
                    SearchResult(
                        id=row["id"],
                        score=float(row["distance"]),
                        vector=vec,
                        metadata=metadata,
                        payload=payload,
                    )
                )
            return results

    def get_vector(
        self,
        collection_name: str,
        vector_id: str,
        include_vector: bool = True,
    ) -> Optional[VectorDocument]:
        with self._lock:
            conn = self._require()
            dim, _ = self._collection_info(collection_name)
            row = conn.execute(
                "SELECT id, vector, metadata, payload FROM vectors"
                " WHERE collection = ? AND id = ?",
                (collection_name, vector_id),
            ).fetchone()
            if row is None:
                return None
            vec = (
                _unpack_vector(row["vector"], dim)
                if include_vector
                else np.array([], dtype=np.float32)
            )
            return VectorDocument(
                id=row["id"],
                vector=vec,
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                payload=json.loads(row["payload"]) if row["payload"] else None,
            )

    def update_vector(
        self,
        collection_name: str,
        vector_id: str,
        vector: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            conn = self._require()
            dim, _ = self._collection_info(collection_name)
            sets: list[str] = []
            params: list[Any] = []
            if vector is not None:
                arr = np.asarray(vector, dtype=np.float32)
                if arr.shape != (dim,):
                    raise ValueError(
                        f"vector dimension mismatch for id={vector_id}: "
                        f"expected {dim}, got {arr.shape}"
                    )
                sets.append("vector = ?")
                params.append(_pack_vector(arr))
            if metadata is not None:
                sets.append("metadata = ?")
                params.append(json.dumps(metadata))
            if payload is not None:
                sets.append("payload = ?")
                params.append(json.dumps(payload))
            if not sets:
                return
            params.extend([collection_name, vector_id])
            # `sets` is built from a fixed set of hard-coded `column = ?`
            # fragments above, never from user input — safe to f-string in.
            conn.execute(
                f"UPDATE vectors SET {', '.join(sets)}"  # nosec B608
                " WHERE collection = ? AND id = ?",
                params,
            )

    def delete_vectors(self, collection_name: str, vector_ids: List[str]) -> None:
        if not vector_ids:
            return
        with self._lock:
            conn = self._require()
            # `placeholders` is just commas + `?` (no user input). The ids
            # themselves are passed as bound parameters.
            placeholders = ",".join("?" * len(vector_ids))
            conn.execute(
                f"DELETE FROM vectors WHERE collection = ? AND id IN ({placeholders})",  # nosec B608
                [collection_name, *vector_ids],
            )

    def count_vectors(self, collection_name: str) -> int:
        with self._lock:
            conn = self._require()
            row = conn.execute(
                "SELECT COUNT(*) FROM vectors WHERE collection = ?",
                (collection_name,),
            ).fetchone()
            return int(row[0]) if row else 0
