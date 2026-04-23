from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from naas_abi.apps.nexus.apps.api.app.services.model_registry import get_all_provider_names
from pydantic import BaseModel, Field

VALID_PROVIDER_TYPES = get_all_provider_names() + ["custom", "abi"]


class Message(BaseModel):
    id: str
    conversation_id: str | None = None
    role: Literal["user", "assistant", "system"]
    content: str
    agent: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None


class Conversation(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    title: str = "New Conversation"
    agent: str = "aia"
    messages: list[Message] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConversationCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(default="New Conversation", min_length=1, max_length=200)
    agent: str = Field(default="aia", min_length=1, max_length=50)


class ProviderConfigRequest(BaseModel):
    id: str
    name: str
    type: str
    enabled: bool
    endpoint: str | None = None
    api_key: str | None = None
    account_id: str | None = None
    model: str

    def model_post_init(self, __context: Any) -> None:
        if self.type not in VALID_PROVIDER_TYPES:
            raise ValueError(
                f"Invalid provider type '{self.type}'. "
                f"Must be one of: {', '.join(sorted(VALID_PROVIDER_TYPES))}"
            )


class MessageRequest(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., max_length=100_000)
    images: list[str] | None = Field(None, max_length=10)
    agent: str | None = None


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(None, max_length=100)
    workspace_id: str | None = Field(None, max_length=100)
    message: str = Field(..., min_length=1, max_length=100_000)
    images: list[str] | None = Field(None, max_length=10)
    messages: list[MessageRequest] = Field(default_factory=list, max_length=200)
    agent: str = Field(default="aia", min_length=1, max_length=50)
    provider: ProviderConfigRequest | None = None
    context: dict[str, Any] | None = None
    system_prompt: str | None = Field(None, max_length=50_000)
    search_enabled: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    message: Message
    context_used: list[str] = Field(default_factory=list)
    provider_used: str | None = None


class ChatIngestMyDriveFileRequest(BaseModel):
    source_path: str = Field(..., min_length=1, max_length=1000)
    workspace_id: str | None = Field(default=None, max_length=100)
    embedding_model: str = Field(default="text-embedding-3-small", min_length=1, max_length=200)
    embedding_dimension: int = Field(default=1536, ge=8, le=4096)


class ChatFileIngestionResponse(BaseModel):
    job_id: str | None = None
    status: str | None = None
    conversation_id: str
    source_path: str
    collection_name: str
    file_sha256: str
    cache_hit: bool
    chunks_count: int
    statuses: list[str] = Field(default_factory=list)
    embedding_model: str
    embedding_dimension: int


class ChatIngestionJobStatusResponse(BaseModel):
    job_id: str
    conversation_id: str
    workspace_id: str
    source_path: str
    status: str
    progress: int | None = None
    cache_hit: bool | None = None
    file_sha256: str | None = None
    collection_name: str | None = None
    chunks_count: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    attempt: int
    max_attempts: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


def to_conversation(row: Any, messages: list[Message] | None = None) -> Conversation:
    return Conversation(
        id=row.id,
        workspace_id=row.workspace_id,
        user_id=row.user_id,
        title=row.title,
        agent=row.agent,
        messages=messages or [],
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def to_message(row: Any) -> Message:
    return Message(
        id=row.id,
        conversation_id=row.conversation_id,
        role=row.role,
        content=row.content,
        agent=row.agent,
        metadata=json.loads(row.metadata_) if row.metadata_ else None,
        created_at=row.created_at,
    )
