"""Unit tests for My Drive Code sandbox adapter."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.secondary.my_drive_filesystem import (
    MyDriveFilesystemAdapter,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drive_roots import my_drive_code_root
from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
    FileContentData,
    FileInfoData,
    FileListResponseData,
)


@pytest.fixture
def files_service():
    service = MagicMock()
    service._is_directory.return_value = True
    service._file_exists.return_value = False
    service.list_files.return_value = FileListResponseData(files=[], path=my_drive_code_root("user-1"))
    return service


class TestMyDriveFilesystemAdapter:
    def test_sandbox_root_is_my_drive_code_folder(self, files_service):
        adapter = MyDriveFilesystemAdapter(files_service=files_service)
        listing = adapter.list_directory(path="", user_id="user-1")
        assert listing.sandbox_root == "naas_abi/my-drive/user-1/code"
        files_service.create_folder.assert_not_called()

    def test_write_creates_file_under_code_root(self, files_service):
        adapter = MyDriveFilesystemAdapter(files_service=files_service)
        files_service.create_file.return_value = FileInfoData(
            name="hello.py",
            path="naas_abi/my-drive/user-1/code/hello.py",
            type="file",
            size=3,
            modified=datetime.now(),
            content_type="text/plain",
        )
        result = adapter.write_file("hello.py", "x=1", user_id="user-1")
        assert result.path == "naas_abi/my-drive/user-1/code/hello.py"
        files_service.create_file.assert_called_once()

    def test_read_file_returns_content(self, files_service):
        adapter = MyDriveFilesystemAdapter(files_service=files_service)
        files_service.read_file.return_value = FileContentData(
            path="naas_abi/my-drive/user-1/code/hello.py",
            content="print('hi')\n",
            content_type="text/plain",
        )
        assert adapter.read_file("hello.py", user_id="user-1") == "print('hi')\n"
