"""Unit tests for the Code filesystem secondary adapter."""

from __future__ import annotations

from uuid import uuid4

import pytest
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.secondary.local_filesystem import (
    LocalFilesystemAdapter,
)
from naas_abi.apps.nexus.apps.api.app.services.code.code__schema import (
    CodePathNotFoundError,
    CodeWriteForbiddenError,
)
from naas_abi.apps.nexus.apps.api.app.services.code.filesystem_service import CodeFilesystemService


@pytest.fixture
def fs_service(tmp_path, monkeypatch):
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "readonly.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setenv("FILESYSTEM_ROOT", str(tmp_path))
    monkeypatch.setenv("SANDBOX_ROOT", "sandbox")
    return CodeFilesystemService(adapter=LocalFilesystemAdapter())


class TestCodeFilesystemService:
    def test_list_sandbox_root(self, fs_service):
        result = fs_service.list_path("sandbox")
        assert result.sandbox_root == "sandbox"
        assert result.path == "sandbox"

    def test_crud_in_sandbox(self, fs_service):
        stamp = uuid4().hex[:8]
        folder = f"sandbox/e2e_folder_{stamp}"
        file_path = f"sandbox/e2e_{stamp}.py"
        renamed = f"{folder}/renamed.py"

        fs_service.create_folder(folder)
        fs_service.write_file(file_path, 'print("v1")\n')
        assert fs_service.read_file(file_path) == 'print("v1")\n'
        fs_service.write_file(file_path, 'print("v2")\n')
        fs_service.rename_path(file_path, renamed)
        fs_service.delete_path(renamed)

    def test_write_blocked_outside_sandbox(self, fs_service):
        with pytest.raises(CodeWriteForbiddenError):
            fs_service.write_file("readonly.txt", "nope")

    def test_user_scoped_sandbox(self, fs_service):
        user_id = "user-test"
        scoped_root = f"sandbox/{user_id}"
        fs_service.create_folder(scoped_root, user_id=user_id)
        file_path = f"{scoped_root}/hello.py"
        fs_service.write_file(file_path, "x = 1\n", user_id=user_id)
        assert fs_service.read_file(file_path) == "x = 1\n"
        listing = fs_service.list_path(scoped_root, user_id=user_id)
        assert listing.sandbox_root == scoped_root

    def test_missing_path_raises(self, fs_service):
        with pytest.raises(CodePathNotFoundError):
            fs_service.read_file("sandbox/does-not-exist.py")
