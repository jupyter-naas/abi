from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.code.code__schema import (
    CodeFSDeleteResultData,
    CodeFSListResponseData,
    CodeFSRenameResultData,
    CodeFSWriteResultData,
)
from naas_abi.apps.nexus.apps.api.app.services.code.port import CodeFilesystemPort


class CodeFilesystemService:
    def __init__(self, adapter: CodeFilesystemPort):
        self.adapter = adapter

    def list_path(self, path: str, user_id: str | None = None) -> CodeFSListResponseData:
        return self.adapter.list_directory(path, user_id=user_id)

    def read_file(self, path: str, user_id: str | None = None) -> str:
        return self.adapter.read_file(path, user_id=user_id)

    def write_file(
        self, path: str, content: str, user_id: str | None = None
    ) -> CodeFSWriteResultData:
        return self.adapter.write_file(path, content, user_id=user_id)

    def create_folder(self, path: str, user_id: str | None = None) -> dict[str, str]:
        return self.adapter.create_folder(path, user_id=user_id)

    def rename_path(
        self, path: str, new_path: str, user_id: str | None = None
    ) -> CodeFSRenameResultData:
        return self.adapter.rename_path(path, new_path, user_id=user_id)

    def delete_path(self, path: str, user_id: str | None = None) -> CodeFSDeleteResultData:
        return self.adapter.delete_path(path, user_id=user_id)
