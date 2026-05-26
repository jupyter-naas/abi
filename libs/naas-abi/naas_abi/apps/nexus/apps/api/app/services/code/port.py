from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from naas_abi.apps.nexus.apps.api.app.services.code.code__schema import (
    CodeFSDeleteResultData,
    CodeFSListResponseData,
    CodeFSRenameResultData,
    CodeFSWriteResultData,
)


class CodeFilesystemPort(ABC):
    @abstractmethod
    def list_directory(
        self, path: str, user_id: str | None = None
    ) -> CodeFSListResponseData:
        pass

    @abstractmethod
    def read_file(self, path: str, user_id: str | None = None) -> str:
        pass

    @abstractmethod
    def write_file(
        self, path: str, content: str, user_id: str | None = None
    ) -> CodeFSWriteResultData:
        pass

    @abstractmethod
    def create_folder(self, path: str, user_id: str | None = None) -> dict[str, str]:
        pass

    @abstractmethod
    def rename_path(
        self, path: str, new_path: str, user_id: str | None = None
    ) -> CodeFSRenameResultData:
        pass

    @abstractmethod
    def delete_path(
        self, path: str, user_id: str | None = None
    ) -> CodeFSDeleteResultData:
        pass


class CodeOpencodePort(ABC):
    @abstractmethod
    async def resolve_base_url(self) -> str:
        pass

    @abstractmethod
    async def health(self) -> dict[str, object]:
        pass

    @abstractmethod
    async def proxy_get(self, path: str) -> object:
        pass

    @abstractmethod
    async def proxy_post(self, path: str, body: dict | None = None) -> object:
        pass

    @abstractmethod
    async def proxy_delete(self, path: str) -> object:
        pass

    @abstractmethod
    async def stream_chat(self, input_data: object) -> AsyncIterator[str]:
        pass

    @abstractmethod
    def get_agent_port(self) -> int:
        pass


class CodeLogsPort(ABC):
    @abstractmethod
    def get_recent_lines(self) -> list[str]:
        pass

    @abstractmethod
    def subscribe(self) -> object:
        pass

    @abstractmethod
    def unsubscribe(self, listener: object) -> None:
        pass
