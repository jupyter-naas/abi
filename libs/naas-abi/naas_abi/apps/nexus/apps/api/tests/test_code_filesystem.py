"""Tests for the Code section filesystem API (/api/filesystem)."""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture
def fs_root(tmp_path, monkeypatch):
    """Isolated writable sandbox for local filesystem backend tests."""
    (tmp_path / "sandbox").mkdir()
    (tmp_path / "readonly.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setenv("FILESYSTEM_ROOT", str(tmp_path))
    monkeypatch.setenv("SANDBOX_ROOT", "sandbox")
    monkeypatch.setenv("CODE_SANDBOX_BACKEND", "local")
    return tmp_path


class TestCodeFilesystem:
    async def test_list_sandbox_root(self, client, test_user, fs_root):
        response = await client.get(
            "/api/filesystem/?path=sandbox",
            headers=test_user["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sandbox_root"] == "sandbox"
        assert data["path"] == "sandbox"
        assert isinstance(data["files"], list)

    async def test_crud_in_sandbox(self, client, test_user, fs_root):
        stamp = uuid4().hex[:8]
        folder = f"sandbox/e2e_folder_{stamp}"
        file_path = f"sandbox/e2e_{stamp}.py"
        renamed = f"{folder}/renamed.py"
        content_v1 = 'print("v1")\n'
        content_v2 = 'print("v2")\n'

        create_folder = await client.post(
            f"/api/filesystem/folder?path={folder}",
            headers=test_user["headers"],
        )
        assert create_folder.status_code == 200

        create_file = await client.put(
            f"/api/filesystem/content?path={file_path}",
            headers=test_user["headers"],
            json={"content": content_v1},
        )
        assert create_file.status_code == 200

        read_file = await client.get(
            f"/api/filesystem/content?path={file_path}",
            headers=test_user["headers"],
        )
        assert read_file.status_code == 200
        assert read_file.text == content_v1

        update_file = await client.put(
            f"/api/filesystem/content?path={file_path}",
            headers=test_user["headers"],
            json={"content": content_v2},
        )
        assert update_file.status_code == 200

        rename_file = await client.post(
            f"/api/filesystem/rename?path={file_path}",
            headers=test_user["headers"],
            json={"new_path": renamed},
        )
        assert rename_file.status_code == 200

        delete_file = await client.delete(
            f"/api/filesystem/content?path={renamed}",
            headers=test_user["headers"],
        )
        assert delete_file.status_code == 200
        assert delete_file.json()["deleted"] is True

    async def test_write_blocked_outside_sandbox(self, client, test_user, fs_root):
        response = await client.put(
            "/api/filesystem/content?path=readonly.txt",
            headers=test_user["headers"],
            json={"content": "nope"},
        )
        assert response.status_code == 403

    async def test_requires_auth(self, client, fs_root):
        response = await client.get("/api/filesystem/?path=sandbox")
        assert response.status_code == 401
