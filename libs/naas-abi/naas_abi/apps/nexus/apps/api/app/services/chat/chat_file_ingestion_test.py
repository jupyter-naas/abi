from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

import pytest

from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_ingestion import (
    ChatFileIngestionError,
    ChatFileIngestionService,
)
from naas_abi_core.services.cache.CachePort import CachedData, CacheNotFoundError
from naas_abi_core.services.cache.CacheService import CacheService

# ---------------------------------------------------------------------------
# In-memory test doubles
# ---------------------------------------------------------------------------


class _MemoryCacheAdapter:
    def __init__(self):
        self.data: dict[str, CachedData] = {}
        self.write_count: dict[str, int] = {}

    def get(self, key: str) -> CachedData:
        if key not in self.data:
            raise CacheNotFoundError(key)
        return self.data[key]

    def set(self, key: str, value: CachedData) -> None:
        self.data[key] = value
        self.write_count[key] = self.write_count.get(key, 0) + 1

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        if key in self.data:
            return False
        self.data[key] = value
        self.write_count[key] = self.write_count.get(key, 0) + 1
        return True

    def delete(self, key: str) -> None:
        if key in self.data:
            del self.data[key]

    def exists(self, key: str) -> bool:
        return key in self.data


class _MemoryObjectStorage:
    def __init__(self):
        self._items: dict[tuple[str, str], bytes] = {}

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self._items[(prefix, key)] = content

    def get_object(self, prefix: str, key: str) -> bytes:
        if (prefix, key) not in self._items:
            from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
            raise Exceptions.ObjectNotFound(f"{prefix}/{key}")
        return self._items[(prefix, key)]


@dataclass
class _VectorStoreCall:
    collection_name: str
    ids_count: int


class _MemoryVectorStore:
    def __init__(self):
        self.collections: dict[str, int] = {}
        self.calls: list[_VectorStoreCall] = []

    def ensure_collection(
        self,
        collection_name: str,
        dimension: int,
        distance_metric: str = "cosine",
    ) -> None:
        self.collections[collection_name] = dimension

    def add_documents(self, collection_name, ids, vectors, metadata=None, payloads=None) -> None:
        self.calls.append(_VectorStoreCall(collection_name=collection_name, ids_count=len(ids)))


def _make_service() -> ChatFileIngestionService:
    return ChatFileIngestionService(
        object_storage=_MemoryObjectStorage(),
        vector_store=_MemoryVectorStore(),
        cache_service=CacheService(_MemoryCacheAdapter()),
    )


# ---------------------------------------------------------------------------
# Minimal DOCX/PPTX builders
# ---------------------------------------------------------------------------

def _minimal_docx(text: str = "Hello from docx") -> bytes:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>'
        f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>'
        '</w:body>'
        '</w:document>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", xml)
    return buf.getvalue()


def _minimal_pptx(text: str = "Hello from pptx") -> bytes:
    a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
        f' xmlns:a="{a_ns}">'
        f'<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld>'
        '</p:sld>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ppt/slides/slide1.xml", xml)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests: cache hit / miss
# ---------------------------------------------------------------------------

def test_upload_and_ingest_uses_cache_on_second_call() -> None:
    service = _make_service()

    first = service.upload_and_ingest(
        user_id="user-1",
        conversation_id="conv-1",
        filename="notes.txt",
        content=b"Hello world\n" * 200,
        embedding_model="hash-v1",
        embedding_dimension=32,
    )
    second = service.ingest_from_path(
        user_id="user-1",
        conversation_id="conv-2",
        source_path=first.source_path,
        embedding_model="hash-v1",
        embedding_dimension=32,
    )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert first.collection_name == "chat_conv-1"
    assert second.collection_name == "chat_conv-2"
    assert first.chunks_count > 0


def test_same_file_different_model_is_cache_miss() -> None:
    """Changing the embedding model must bypass the existing cache entry."""
    service = _make_service()

    first = service.upload_and_ingest(
        user_id="user-1",
        conversation_id="conv-1",
        filename="notes.txt",
        content=b"Hello world\n" * 200,
        embedding_model="hash-v1",
        embedding_dimension=32,
    )
    second = service.ingest_from_path(
        user_id="user-1",
        conversation_id="conv-2",
        source_path=first.source_path,
        embedding_model="hash-v1",
        embedding_dimension=64,   # different dimension → different cache key
    )

    assert first.cache_hit is False
    assert second.cache_hit is False


def test_multiple_files_share_same_collection() -> None:
    vs = _MemoryVectorStore()
    os_ = _MemoryObjectStorage()
    cache = CacheService(_MemoryCacheAdapter())
    service = ChatFileIngestionService(
        object_storage=os_, vector_store=vs, cache_service=cache
    )

    for i, name in enumerate(["a.txt", "b.txt"]):
        service.upload_and_ingest(
            user_id="u",
            conversation_id="conv-shared",
            filename=name,
            content=f"Content {i}\n".encode() * 200,
            embedding_model="hash-v1",
            embedding_dimension=32,
        )

    collection_names = {c.collection_name for c in vs.calls}
    assert collection_names == {"chat_conv-shared"}


def test_idempotent_ingest_same_file_twice() -> None:
    """Ingesting the same file twice with the same model writes to cache only once."""
    adapter = _MemoryCacheAdapter()
    service = ChatFileIngestionService(
        object_storage=_MemoryObjectStorage(),
        vector_store=_MemoryVectorStore(),
        cache_service=CacheService(adapter),
    )

    content = b"Stable content\n" * 300
    service.upload_and_ingest(
        user_id="u", conversation_id="c1", filename="f.txt",
        content=content, embedding_model="hash-v1", embedding_dimension=32,
    )
    service.upload_and_ingest(
        user_id="u", conversation_id="c2", filename="f.txt",
        content=content, embedding_model="hash-v1", embedding_dimension=32,
    )

    # The embedding cache entry should have been written exactly once
    written_keys = [k for k, cnt in adapter.write_count.items() if k.startswith("embeddings:")]
    assert len(written_keys) == 1
    assert adapter.write_count[written_keys[0]] == 1


# ---------------------------------------------------------------------------
# Tests: authorization / path validation
# ---------------------------------------------------------------------------

def test_ingest_from_path_rejects_cross_user_path() -> None:
    service = _make_service()
    with pytest.raises(ChatFileIngestionError, match="belong to user"):
        service.ingest_from_path(
            user_id="user-1",
            conversation_id="c",
            source_path="my-drive/user-2/uploads/evil.txt",
            embedding_model="hash-v1",
            embedding_dimension=32,
        )


def test_ingest_from_path_rejects_path_traversal() -> None:
    service = _make_service()
    with pytest.raises(ChatFileIngestionError, match="belong to user"):
        service.ingest_from_path(
            user_id="user-1",
            conversation_id="c",
            source_path="my-drive/user-1/../../etc/passwd",
            embedding_model="hash-v1",
            embedding_dimension=32,
        )


def test_upload_empty_filename_falls_back_to_untitled() -> None:
    """An empty filename is stored as 'untitled' (no extension → unsupported type error)."""
    service = _make_service()
    with pytest.raises(ChatFileIngestionError, match="Unsupported file type"):
        service.upload_and_ingest(
            user_id="u", conversation_id="c", filename="",
            content=b"Hello world\n" * 200, embedding_model="hash-v1", embedding_dimension=32,
        )


def test_upload_filename_with_path_separator_keeps_last_segment() -> None:
    """Filenames with path separators are reduced to their last component."""
    service = _make_service()
    result = service.upload_and_ingest(
        user_id="u", conversation_id="c", filename="../../notes.txt",
        content=b"Hello world\n" * 200, embedding_model="hash-v1", embedding_dimension=32,
    )
    # Only the final component must appear in the stored path
    assert "etc" not in result.source_path
    assert result.source_path.endswith("notes.txt")


# ---------------------------------------------------------------------------
# Tests: file conversion
# ---------------------------------------------------------------------------

def test_ingest_docx_content() -> None:
    service = _make_service()
    result = service.upload_and_ingest(
        user_id="u",
        conversation_id="c",
        filename="doc.docx",
        content=_minimal_docx("Hello DOCX world"),
        embedding_model="hash-v1",
        embedding_dimension=32,
    )
    assert result.chunks_count > 0
    assert result.cache_hit is False


def test_ingest_pptx_content() -> None:
    service = _make_service()
    result = service.upload_and_ingest(
        user_id="u",
        conversation_id="c",
        filename="slides.pptx",
        content=_minimal_pptx("Hello PPTX world"),
        embedding_model="hash-v1",
        embedding_dimension=32,
    )
    assert result.chunks_count > 0


def test_ingest_unsupported_extension_raises() -> None:
    service = _make_service()
    with pytest.raises(ChatFileIngestionError, match="Unsupported file type"):
        service.upload_and_ingest(
            user_id="u", conversation_id="c", filename="archive.zip",
            content=b"PK\x03\x04", embedding_model="hash-v1", embedding_dimension=32,
        )


def test_ingest_bad_docx_raises() -> None:
    service = _make_service()
    with pytest.raises(ChatFileIngestionError, match="Invalid DOCX"):
        service.upload_and_ingest(
            user_id="u", conversation_id="c", filename="bad.docx",
            content=b"not a zip", embedding_model="hash-v1", embedding_dimension=32,
        )


def _minimal_xlsx(sheets: dict[str, list[list[object]]]) -> bytes:
    """Build an in-memory .xlsx with the given {sheet_name: [[row]]} data."""
    import openpyxl

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default empty sheet
    for sheet_name, rows in sheets.items():
        ws = wb.create_sheet(title=sheet_name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_ingest_xlsx_single_sheet() -> None:
    """A single-sheet workbook produces a Markdown table with the sheet as heading."""
    service = _make_service()
    content = _minimal_xlsx({
        "Sales": [
            ["Name", "Q1", "Q2"],
            ["Alice", 100, 200],
            ["Bob", 150, 250],
        ]
    })
    result = service.upload_and_ingest(
        user_id="u", conversation_id="c", filename="report.xlsx",
        content=content, embedding_model="hash-v1", embedding_dimension=32,
    )
    assert result.chunks_count > 0
    assert result.cache_hit is False


def test_ingest_xlsx_multiple_sheets() -> None:
    """Multi-sheet workbooks include a heading per sheet."""
    service = _make_service()
    content = _minimal_xlsx({
        "Sheet1": [["A", "B"], [1, 2]],
        "Sheet2": [["X", "Y"], [3, 4]],
    })
    result = service.upload_and_ingest(
        user_id="u", conversation_id="c", filename="multi.xlsx",
        content=content, embedding_model="hash-v1", embedding_dimension=32,
    )
    assert result.chunks_count > 0


def test_ingest_xlsx_bad_content_raises() -> None:
    service = _make_service()
    with pytest.raises(ChatFileIngestionError, match="Invalid XLSX"):
        service.upload_and_ingest(
            user_id="u", conversation_id="c", filename="bad.xlsx",
            content=b"not an xlsx", embedding_model="hash-v1", embedding_dimension=32,
        )
