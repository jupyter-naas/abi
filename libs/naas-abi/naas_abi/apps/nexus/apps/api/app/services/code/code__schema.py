from __future__ import annotations

from dataclasses import dataclass


class CodeDomainError(Exception):
    pass


class CodeInvalidPathError(CodeDomainError):
    pass


class CodePathOutsideRootError(CodeDomainError):
    pass


class CodePathNotFoundError(CodeDomainError):
    pass


class CodePathNotDirectoryError(CodeDomainError):
    pass


class CodePathNotFileError(CodeDomainError):
    pass


class CodeWriteForbiddenError(CodeDomainError):
    def __init__(self, sandbox_root: str):
        self.sandbox_root = sandbox_root
        super().__init__(
            f"Write access restricted to {sandbox_root}/ — read-only outside sandbox"
        )


class CodePathAlreadyExistsError(CodeDomainError):
    pass


class CodeFilesystemOSError(CodeDomainError):
    pass


class CodeOpencodeUnavailableError(CodeDomainError):
    pass


@dataclass(frozen=True)
class CodeFSEntryData:
    name: str
    path: str
    type: str
    size: int
    modified: float
    writable: bool


@dataclass(frozen=True)
class CodeFSListResponseData:
    files: list[CodeFSEntryData]
    path: str
    sandbox_root: str


@dataclass(frozen=True)
class CodeFSWriteResultData:
    path: str
    size: int


@dataclass(frozen=True)
class CodeFSRenameResultData:
    old_path: str
    new_path: str


@dataclass(frozen=True)
class CodeFSDeleteResultData:
    path: str
    deleted: bool


@dataclass(frozen=True)
class CodeOpencodeChatInput:
    message: str
    user_id: str = ""
    session_id: str = ""
    model_provider_id: str = ""
    model_id: str = ""
    agent: str = ""


@dataclass(frozen=True)
class CodeOpencodeDefaultModelData:
    provider_id: str
    model_id: str
    name: str
    source: str
