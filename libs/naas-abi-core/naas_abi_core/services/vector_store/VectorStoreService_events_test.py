# mypy: disable-error-code="arg-type,misc"
"""Tests for VectorStoreService event publishing."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pytest

from .IVectorStorePort import IVectorStorePort, SearchResult, VectorDocument
from .VectorStoreService import VectorStoreService
from .ontologies.modules.VectorStoreEventOntology import (
    CollectionDeleted,
    CollectionEnsured,
    DocumentsAdded,
    DocumentsDeleted,
    DocumentUpdated,
    VectorStoreError,
)


class _MemoryAdapter(IVectorStorePort):
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, VectorDocument]] = {}

    def initialize(self) -> None:
        pass

    def create_collection(
        self,
        collection_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs,
    ) -> None:
        self.collections.setdefault(collection_name, {})

    def delete_collection(self, collection_name: str) -> None:
        self.collections.pop(collection_name, None)

    def list_collections(self) -> List[str]:
        return list(self.collections.keys())

    def store_vectors(
        self, collection_name: str, documents: List[VectorDocument]
    ) -> None:
        coll = self.collections.setdefault(collection_name, {})
        for doc in documents:
            coll[doc.id] = doc

    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_vectors: bool = False,
        include_metadata: bool = True,
    ) -> List[SearchResult]:
        return []

    def get_vector(
        self,
        collection_name: str,
        vector_id: str,
        include_vector: bool = True,
    ) -> Optional[VectorDocument]:
        return self.collections.get(collection_name, {}).get(vector_id)

    def update_vector(
        self,
        collection_name: str,
        vector_id: str,
        vector: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        coll = self.collections.setdefault(collection_name, {})
        existing = coll.get(vector_id)
        if existing is None:
            existing = VectorDocument(
                id=vector_id, vector=vector if vector is not None else np.array([]),
                metadata=metadata or {}, payload=payload,
            )
        if vector is not None:
            existing.vector = vector
        if metadata is not None:
            existing.metadata = metadata
        if payload is not None:
            existing.payload = payload
        coll[vector_id] = existing

    def delete_vectors(
        self, collection_name: str, vector_ids: List[str]
    ) -> None:
        coll = self.collections.get(collection_name, {})
        for vid in vector_ids:
            coll.pop(vid, None)

    def count_vectors(self, collection_name: str) -> int:
        return len(self.collections.get(collection_name, {}))

    def close(self) -> None:
        pass


class _BrokenAdapter(_MemoryAdapter):
    def create_collection(self, *args, **kwargs) -> None:
        raise OSError("backend down")

    def delete_collection(self, *args, **kwargs) -> None:
        raise OSError("backend down")

    def store_vectors(self, *args, **kwargs) -> None:
        raise OSError("backend down")

    def update_vector(self, *args, **kwargs) -> None:
        raise OSError("backend down")

    def delete_vectors(self, *args, **kwargs) -> None:
        raise OSError("backend down")


class _FakeEventService:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)


class _FakeServices:
    def __init__(self, events: _FakeEventService | None = None) -> None:
        self._events = events

    def events_available(self) -> bool:
        return self._events is not None

    @property
    def events(self) -> _FakeEventService:
        assert self._events is not None
        return self._events


def _wired() -> tuple[VectorStoreService, _FakeEventService]:
    svc = VectorStoreService(_MemoryAdapter())
    events = _FakeEventService()
    svc.set_services(_FakeServices(events))
    return svc, events


def test_no_events_when_unwired() -> None:
    svc = VectorStoreService(_MemoryAdapter())
    svc.ensure_collection("c", 4)
    svc.add_documents("c", ["d1"], [np.zeros(4)])
    svc.delete_documents("c", ["d1"])
    svc.delete_collection("c")


def test_no_events_when_events_unavailable() -> None:
    svc = VectorStoreService(_MemoryAdapter())
    svc.set_services(_FakeServices(events=None))
    svc.ensure_collection("c", 4)
    svc.add_documents("c", ["d1"], [np.zeros(4)])


def test_ensure_collection_emits_collection_ensured() -> None:
    svc, events = _wired()
    svc.ensure_collection("col", 8)

    assert len(events.published) == 1
    evt = events.published[0]
    assert isinstance(evt, CollectionEnsured)
    assert evt.collection_name == "col"


def test_add_documents_emits_documents_added_with_count() -> None:
    svc, events = _wired()
    svc.ensure_collection("col", 4)
    events.published.clear()

    svc.add_documents(
        "col", ["a", "b", "c"], [np.zeros(4), np.ones(4), np.zeros(4)]
    )

    added = [e for e in events.published if isinstance(e, DocumentsAdded)]
    assert len(added) == 1
    assert added[0].collection_name == "col"
    assert added[0].document_count == 3


def test_update_document_emits_document_updated() -> None:
    svc, events = _wired()
    svc.ensure_collection("col", 4)
    svc.add_documents("col", ["doc1"], [np.zeros(4)])
    events.published.clear()

    svc.update_document("col", "doc1", metadata={"k": "v"})

    updated = [e for e in events.published if isinstance(e, DocumentUpdated)]
    assert len(updated) == 1
    assert updated[0].collection_name == "col"
    assert updated[0].document_id == "doc1"


def test_delete_documents_emits_documents_deleted_with_count() -> None:
    svc, events = _wired()
    svc.ensure_collection("col", 4)
    svc.add_documents(
        "col", ["a", "b"], [np.zeros(4), np.zeros(4)]
    )
    events.published.clear()

    svc.delete_documents("col", ["a", "b"])

    deleted = [e for e in events.published if isinstance(e, DocumentsDeleted)]
    assert len(deleted) == 1
    assert deleted[0].collection_name == "col"
    assert deleted[0].document_count == 2


def test_delete_collection_emits_collection_deleted() -> None:
    svc, events = _wired()
    svc.ensure_collection("col", 4)
    events.published.clear()

    svc.delete_collection("col")

    deleted = [e for e in events.published if isinstance(e, CollectionDeleted)]
    assert len(deleted) == 1
    assert deleted[0].collection_name == "col"


def test_adapter_exception_emits_vector_store_error_and_reraises() -> None:
    svc = VectorStoreService(_BrokenAdapter())
    events = _FakeEventService()
    svc.set_services(_FakeServices(events))

    with pytest.raises(OSError):
        svc.add_documents("col", ["a"], [np.zeros(4)])

    errors = [e for e in events.published if isinstance(e, VectorStoreError)]
    assert len(errors) == 1
    assert errors[0].collection_name == "col"
    assert errors[0].operation == "add_documents"
    assert "backend down" in (errors[0].message or "")
    # no success event for this operation
    assert not any(isinstance(e, DocumentsAdded) for e in events.published)


def test_publisher_exception_does_not_break_operation() -> None:
    class _ExplodingEvents:
        def publish(self, event):
            raise RuntimeError("event bus down")

    svc = VectorStoreService(_MemoryAdapter())
    svc.set_services(_FakeServices(events=_ExplodingEvents()))

    svc.ensure_collection("col", 4)
    svc.add_documents("col", ["a"], [np.zeros(4)])
    assert svc.get_collection_size("col") == 1
