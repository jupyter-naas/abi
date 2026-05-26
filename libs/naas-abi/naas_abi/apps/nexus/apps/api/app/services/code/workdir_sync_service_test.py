"""Unit tests for Code workdir sync."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.code.workdir_sync_service import (
    CodeWorkdirSyncService,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drive_roots import my_drive_code_root


@pytest.fixture
def sync_service(tmp_path, monkeypatch):
    monkeypatch.setenv("CODE_WORKDIR_SYNC_ROOT", str(tmp_path / "sandbox"))
    monkeypatch.setenv("OPENCODE_HOST_WORKDIR", str(tmp_path / "host-sandbox"))
    files = MagicMock()
    files._is_directory.return_value = True
    files._collect_directory_tree.return_value = (
        [f"{my_drive_code_root('user-1')}/hello.py"],
        [my_drive_code_root("user-1")],
    )
    files._read_bytes.return_value = b'print("hi")\n'
    files._file_exists.return_value = False
    return CodeWorkdirSyncService(files_service=files)


class TestCodeWorkdirSyncService:
    def test_pull_writes_files_locally(self, sync_service):
        result = sync_service.pull("user-1")
        local_file = Path(result.local_path) / "hello.py"
        assert local_file.exists()
        assert local_file.read_text() == 'print("hi")\n'
        assert result.files_pulled == 1

    def test_opencode_workdir_maps_to_host_path(self, sync_service, tmp_path):
        host_path = sync_service.opencode_workdir("user-1")
        assert host_path.startswith(str(tmp_path / "host-sandbox"))
        assert host_path.endswith("/user-1/code")
