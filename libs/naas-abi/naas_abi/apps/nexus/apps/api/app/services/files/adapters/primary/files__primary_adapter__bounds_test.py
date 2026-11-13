"""The files routes bound what one request costs the API process: uploads are
read up to their cap, and previews and extractions run off the event loop, a
few at a time, a bounded number a minute per caller.

The real router over a real IAM and a filesystem object storage (the harness of
``files__primary_adapter__iam_test.py``).
"""

from __future__ import annotations

import asyncio
import io
import threading
import time
import zipfile

import pytest
from naas_abi.apps.nexus.apps.api.app.core.bounded_work import BoundedWork
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary import (
    files__primary_adapter__FastAPI as files_api,
)
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__iam_test import (  # noqa: E501
    WS1,
    _client_factory,
    drives,  # noqa: F401 - fixture
    storage,  # noqa: F401 - fixture
    ws,
)
from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import PdfPreviewData
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService


@pytest.fixture
def client(team, storage, drives):  # noqa: F811
    return _client_factory(storage)


@pytest.fixture(autouse=True)
def fresh_bounds(monkeypatch):
    monkeypatch.setattr(
        files_api, "_OFFICE_PREVIEW", BoundedWork("office previews", concurrent=2, per_user=20)
    )
    monkeypatch.setattr(
        files_api, "_ARCHIVE_EXTRACT", BoundedWork("archive extractions", concurrent=2, per_user=10)
    )


@pytest.mark.asyncio
async def test_upload_keeps_memory_under_the_cap(client, storage, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(FilesService, "max_upload_size", 2 * 1024 * 1024)
    handed: list[int] = []
    real = FilesService.upload_file

    def spy(self, filename, path, content, content_type):
        handed.append(len(content))
        return real(self, filename, path, content, content_type)

    monkeypatch.setattr(FilesService, "upload_file", spy)
    async with client("member") as http:
        too_big = await http.post(
            "/api/files/upload",
            data={"path": "", "workspace_id": "ws-1"},
            files={"file": ("big.bin", b"\0" * (5 * 1024 * 1024), "application/octet-stream")},
        )
        fits = await http.post(
            "/api/files/upload",
            data={"path": "", "workspace_id": "ws-1"},
            files={"file": ("ok.bin", b"\1" * 1024, "application/octet-stream")},
        )
    assert too_big.status_code == 413
    assert fits.status_code == 200
    assert handed == [1024]  # the oversized body never reached the service


@pytest.mark.asyncio
async def test_preview_keeps_the_event_loop_free(client, storage, monkeypatch) -> None:  # noqa: F811
    storage.put_object(WS1, "deck.docx", b"PK office bytes")
    seen: dict[str, object] = {}

    def slow_preview(self, path: str) -> PdfPreviewData:
        seen["thread"] = threading.get_ident()
        time.sleep(1.0)
        return PdfPreviewData(content=b"%PDF-1.4", filename="deck.pdf")

    monkeypatch.setattr(FilesService, "preview_file_as_pdf", slow_preview)
    async with client("member") as http:
        loop_thread = threading.get_ident()
        preview = asyncio.create_task(http.get("/api/files/preview/pdf/deck.docx", params=ws()))
        await asyncio.sleep(0.2)
        started = time.monotonic()
        listing = await http.get("/api/files/", params=ws())
        listing_took = time.monotonic() - started
        assert (await preview).status_code == 200
    assert listing.status_code == 200
    assert listing_took < 0.8
    assert seen["thread"] != loop_thread


@pytest.mark.asyncio
async def test_previews_keep_a_per_caller_rate(client, storage, monkeypatch) -> None:  # noqa: F811
    storage.put_object(WS1, "deck.docx", b"PK office bytes")
    monkeypatch.setattr(
        files_api, "_OFFICE_PREVIEW", BoundedWork("office previews", concurrent=2, per_user=3)
    )
    monkeypatch.setattr(
        FilesService,
        "preview_file_as_pdf",
        lambda self, path: PdfPreviewData(content=b"%PDF-1.4", filename="deck.pdf"),
    )
    async with client("member") as http:
        codes = [
            (await http.get("/api/files/preview/pdf/deck.docx", params=ws())).status_code
            for _ in range(4)
        ]
    assert codes == [200, 200, 200, 429]


@pytest.mark.asyncio
async def test_extract_keeps_every_member_counted(client, storage, monkeypatch) -> None:  # noqa: F811
    monkeypatch.setattr(FilesService, "max_extract_files", 50)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for i in range(51):
            zf.writestr(f"d{i}/", b"")
    storage.put_object(WS1, "dirs.zip", buffer.getvalue())
    async with client("member") as http:
        response = await http.post("/api/files/extract/dirs.zip", params=ws())
    assert response.status_code == 413
    assert "too many entries" in response.text
    service = FilesService(storage=storage)
    assert service._file_exists(f"{WS1}/dirs.zip")  # the archive itself stays
    assert not service._is_directory(f"{WS1}/dirs")  # and nothing was extracted
