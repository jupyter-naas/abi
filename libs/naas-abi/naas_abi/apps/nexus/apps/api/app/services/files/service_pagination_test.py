from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


def _make_files_service(tmp_path) -> FilesService:
    adapter = ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path))
    storage = ObjectStorageService(adapter=adapter)
    return FilesService(storage=storage)


def _seed(files_service: FilesService, count: int) -> None:
    # Zero-padded names so the alphabetical listing order is deterministic.
    for i in range(count):
        files_service.create_file(
            path=f"dir/file-{i:03d}.txt", content=str(i), content_type="text/plain"
        )


def test_list_files_without_limit_returns_all_entries(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    _seed(files_service, 5)

    result = files_service.list_files(path="dir")

    assert result.total == 5
    assert len(result.files) == 5


def test_list_files_limit_returns_first_page_and_full_total(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    _seed(files_service, 12)

    result = files_service.list_files(path="dir", limit=5, offset=0)

    assert result.total == 12
    assert [f.name for f in result.files] == [
        "file-000.txt",
        "file-001.txt",
        "file-002.txt",
        "file-003.txt",
        "file-004.txt",
    ]


def test_list_files_offset_returns_following_page(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    _seed(files_service, 12)

    result = files_service.list_files(path="dir", limit=5, offset=10)

    assert result.total == 12
    # Only the last two entries remain in the final page.
    assert [f.name for f in result.files] == ["file-010.txt", "file-011.txt"]


def test_list_files_offset_past_end_returns_empty_page_with_total(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    _seed(files_service, 3)

    result = files_service.list_files(path="dir", limit=5, offset=50)

    assert result.total == 3
    assert result.files == []


def test_list_files_search_filters_by_name_case_insensitively(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    files_service.create_file(path="dir/Report-Q1.txt", content="a", content_type="text/plain")
    files_service.create_file(path="dir/report-q2.txt", content="b", content_type="text/plain")
    files_service.create_file(path="dir/notes.md", content="c", content_type="text/markdown")

    result = files_service.list_files(path="dir", search="REPORT")

    assert result.total == 2
    assert sorted(f.name for f in result.files) == ["Report-Q1.txt", "report-q2.txt"]


def test_list_files_search_total_reflects_matches_and_pages_over_them(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    _seed(files_service, 20)  # file-000.txt .. file-019.txt
    for name in ("alpha.txt", "beta.txt"):
        files_service.create_file(path=f"dir/{name}", content="x", content_type="text/plain")

    # "file" matches only the 20 seeded files, not alpha/beta.
    page = files_service.list_files(path="dir", search="file", limit=5, offset=0)
    assert page.total == 20
    assert [f.name for f in page.files] == [
        "file-000.txt",
        "file-001.txt",
        "file-002.txt",
        "file-003.txt",
        "file-004.txt",
    ]

    last = files_service.list_files(path="dir", search="file", limit=5, offset=15)
    assert last.total == 20
    assert [f.name for f in last.files] == [
        "file-015.txt",
        "file-016.txt",
        "file-017.txt",
        "file-018.txt",
        "file-019.txt",
    ]


def test_list_files_blank_search_is_ignored(tmp_path) -> None:
    files_service = _make_files_service(tmp_path)
    _seed(files_service, 4)

    result = files_service.list_files(path="dir", search="   ")

    assert result.total == 4
    assert len(result.files) == 4
