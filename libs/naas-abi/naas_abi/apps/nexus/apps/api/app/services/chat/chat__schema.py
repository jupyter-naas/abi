from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

ChatRole = Literal["user", "assistant", "system"]


class ChatDomainError(Exception):
    pass


class ChatNotFound(ChatDomainError):
    pass


class ChatForbidden(ChatDomainError):
    pass


class InvalidChatInput(ChatDomainError):
    pass


class ProviderUnavailable(ChatDomainError):
    pass


@dataclass(frozen=True)
class ChatInputMessage:
    role: ChatRole
    content: str
    images: list[str] | None = None
    agent: str | None = None


@dataclass(frozen=True)
class ChatProviderConfigInput:
    id: str
    name: str
    type: str
    enabled: bool
    model: str
    endpoint: str | None = None
    api_key: str | None = None
    account_id: str | None = None


@dataclass(frozen=True)
class CompleteChatInput:
    message: str
    agent: str
    workspace_id: str | None = None
    conversation_id: str | None = None
    messages: list[ChatInputMessage] = field(default_factory=list)
    images: list[str] | None = None
    provider: ChatProviderConfigInput | None = None
    system_prompt: str | None = None
    context: dict | None = None
    search_enabled: bool = False


@dataclass(frozen=True)
class CompleteChatResult:
    conversation_id: str
    assistant_message_id: str
    assistant_content: str
    assistant_agent: str
    provider_used: str | None
    created_at: datetime
