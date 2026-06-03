"""ObjectStorageSearchSource — search over files in object storage.

SCAFFOLD. Real implementation needs:

- A text-extraction pipeline (PDF, DOCX, plain text, images-with-OCR) keyed
  off MIME type. Pulled out as a separate `IDocumentExtractor` port so the
  adapter doesn't grow a multi-format parser; extractors register by MIME.
- A backing index — likely a vector store (LanceDB / Qdrant) so we can do
  semantic + filename + path search. Plain BM25 over `path + title + body`
  is fine for v1.
- Subscription to object-storage mutation events (created / deleted) to keep
  the index in sync. Publish `SearchIndexFailed` on any failure inside the
  pipeline; the upstream event was fine — only the index op failed.
- A `reindex()` that scans the bucket once at boot/setup so the index is not
  permanently behind. Critical: events only cover what happened after we
  subscribed.
"""

from __future__ import annotations

from typing import Any, Iterator

from naas_abi_core.services.search.SearchPorts import (
    Document,
    ISearchSource,
    SearchHit,
)


class ObjectStorageSearchSource(ISearchSource):
    def __init__(self, object_storage: Any, name: str = "object_storage"):
        # `object_storage` is left as `Any` until we settle on which
        # ObjectStorageService method-set we depend on. Keeps the stub from
        # falsely advertising a dependency we haven't actually used.
        self._object_storage = object_storage
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def search(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> Iterator[SearchHit]:
        # TODO: query the backing index. For v1 a path/name substring match
        # against `list_objects()` is a usable bootstrap that ships without
        # any index infrastructure — slow, but proves the wiring.
        return iter([])

    def supports_indexing(self) -> bool:
        return True

    def index(self, document: Document) -> None:
        raise NotImplementedError("ObjectStorageSearchSource: index path not implemented yet")

    def remove(self, document_id: str) -> None:
        raise NotImplementedError("ObjectStorageSearchSource: index path not implemented yet")

    def reindex(self) -> int:
        raise NotImplementedError("ObjectStorageSearchSource: reindex path not implemented yet")
