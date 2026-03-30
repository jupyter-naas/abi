from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

SecretCategory = Literal["api_keys", "credentials", "tokens", "other"]


@dataclass(frozen=True)
class SecretCreateInput:
    workspace_id: str
    key: str
    value: str
    description: str = ""
    category: SecretCategory = "other"


@dataclass(frozen=True)
class SecretUpdateInput:
    value: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class SecretBulkImportInput:
    workspace_id: str
    env_content: str


@dataclass(frozen=True)
class SecretOutput:
    id: str
    workspace_id: str
    key: str
    masked_value: str
    description: str
    category: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class SecretBulkImportResult:
    imported: int
    updated: int


@dataclass
class SecretAlreadyExistsError(ValueError):
    key: str


@dataclass
class SecretNotFoundError(ValueError):
    secret_id: str
