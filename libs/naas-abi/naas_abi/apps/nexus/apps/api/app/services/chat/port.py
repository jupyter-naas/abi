from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatConversationRecord:
    id: str
    workspace_id: str
    user_id: str
    title: str
    agent: str
    created_at: datetime
    updated_at: datetime
    pinned: bool = False
    archived: bool = False


@dataclass
class ChatMessageRecord:
    id: str
    conversation_id: str
    role: str
    content: str
    agent: str | None
    metadata_: str | None
    created_at: datetime


@dataclass
class ChatAgentRecord:
    id: str
    workspace_id: str
    name: str
    class_name: str | None
    model_id: str | None
    provider: str | None


@dataclass
class ChatInferenceServerRecord:
    id: str
    workspace_id: str
    name: str
    type: str
    endpoint: str
    api_key: str | None


@dataclass
class ChatSecretRecord:
    encrypted_value: str


class ChatPersistencePort(ABC):
    @abstractmethod
    async def list_conversations_by_workspace(
        self, workspace_id: str, user_id: str, limit: int, offset: int
    ) -> list[ChatConversationRecord]:
        pass

    @abstractmethod
    async def create_conversation(
        self,
        conversation_id: str,
        workspace_id: str,
        user_id: str,
        title: str,
        agent: str,
        now: datetime,
    ) -> ChatConversationRecord:
        pass

    @abstractmethod
    async def get_conversation_by_id(
        self, conversation_id: str
    ) -> ChatConversationRecord | None:
        pass

    @abstractmethod
    async def get_conversation_by_id_for_user(
        self, conversation_id: str, user_id: str
    ) -> ChatConversationRecord | None:
        pass

    @abstractmethod
    async def update_conversation_agent(
        self, conversation_id: str, agent: str, now: datetime
    ) -> None:
        pass

    @abstractmethod
    async def update_conversation_fields(
        self,
        conversation_id: str,
        now: datetime,
        title: str | None = None,
        pinned: bool | None = None,
        archived: bool | None = None,
    ) -> None:
        pass

    @abstractmethod
    async def touch_conversation(self, conversation_id: str, now: datetime) -> None:
        pass

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> bool:
        pass

    @abstractmethod
    async def list_messages_by_conversation(
        self, conversation_id: str
    ) -> list[ChatMessageRecord]:
        pass

    @abstractmethod
    async def create_message(
        self,
        message_id: str,
        conversation_id: str,
        role: str,
        content: str,
        created_at: datetime,
        agent: str | None = None,
    ) -> None:
        pass

    @abstractmethod
    async def delete_messages_by_conversation(self, conversation_id: str) -> None:
        pass

    @abstractmethod
    async def update_message_content(self, message_id: str, content: str) -> bool:
        pass

    @abstractmethod
    async def get_agent_by_id(self, agent_id: str) -> ChatAgentRecord | None:
        pass

    @abstractmethod
    async def list_agent_names_by_ids(self, agent_ids: set[str]) -> dict[str, str]:
        pass

    @abstractmethod
    async def get_enabled_workspace_abi_server(
        self, workspace_id: str
    ) -> ChatInferenceServerRecord | None:
        pass

    @abstractmethod
    async def get_workspace_secret(
        self, workspace_id: str, key: str
    ) -> ChatSecretRecord | None:
        pass
