from __future__ import annotations

from collections.abc import Callable

from naas_abi.apps.nexus.apps.api.app.models import (
    AgentConfigModel,
    ConversationModel,
    InferenceServerModel,
    MessageModel,
    SecretModel,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.port import (
    ChatAgentRecord,
    ChatConversationRecord,
    ChatInferenceServerRecord,
    ChatMessageRecord,
    ChatPersistencePort,
    ChatSecretRecord,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncSession | None]


class ChatSecondaryAdapterPostgres(ChatPersistencePort):
    def __init__(self, db: AsyncSession | None = None, db_getter: AsyncSessionGetter | None = None):
        self._db = db
        self._db_getter = db_getter

    @property
    def db(self) -> AsyncSession:
        if self._db is not None:
            return self._db
        if self._db_getter is None:
            raise RuntimeError("ChatSecondaryAdapterPostgres has no database binding")
        db = self._db_getter()
        if db is None:
            raise RuntimeError("No database session bound in ServiceRegistry context")
        return db

    @staticmethod
    def _to_conversation_record(model: ConversationModel) -> ChatConversationRecord:
        return ChatConversationRecord(
            id=model.id,
            workspace_id=model.workspace_id,
            user_id=model.user_id,
            title=model.title,
            agent=model.agent,
            created_at=model.created_at,
            updated_at=model.updated_at,
            pinned=bool(model.pinned),
            archived=bool(model.archived),
        )

    @staticmethod
    def _to_message_record(model: MessageModel) -> ChatMessageRecord:
        return ChatMessageRecord(
            id=model.id,
            conversation_id=model.conversation_id,
            role=model.role,
            content=model.content,
            agent=model.agent,
            metadata_=model.metadata_,
            created_at=model.created_at,
        )

    async def list_conversations_by_workspace(
        self, workspace_id: str, user_id: str, limit: int, offset: int
    ) -> list[ChatConversationRecord]:
        result = await self.db.execute(
            select(ConversationModel)
            .where(ConversationModel.workspace_id == workspace_id)
            .where(ConversationModel.user_id == user_id)
            .order_by(ConversationModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_conversation_record(row) for row in result.scalars().all()]

    async def create_conversation(
        self,
        conversation_id: str,
        workspace_id: str,
        user_id: str,
        title: str,
        agent: str,
        now,
    ) -> ChatConversationRecord:
        row = ConversationModel(
            id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            agent=agent,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        await self.db.flush()
        return self._to_conversation_record(row)

    async def get_conversation_by_id(self, conversation_id: str) -> ChatConversationRecord | None:
        result = await self.db.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        row = result.scalar_one_or_none()
        return self._to_conversation_record(row) if row else None

    async def get_conversation_by_id_for_user(
        self, conversation_id: str, user_id: str
    ) -> ChatConversationRecord | None:
        result = await self.db.execute(
            select(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .where(ConversationModel.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        return self._to_conversation_record(row) if row else None

    async def update_conversation_agent(self, conversation_id: str, agent: str, now) -> None:
        result = await self.db.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        row = result.scalar_one_or_none()
        if row:
            row.agent = agent
            row.updated_at = now
            await self.db.flush()

    async def update_conversation_fields(
        self,
        conversation_id: str,
        now,
        title: str | None = None,
        pinned: bool | None = None,
        archived: bool | None = None,
    ) -> None:
        result = await self.db.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            return

        if title is not None:
            row.title = title
        if pinned is not None:
            row.pinned = pinned
        if archived is not None:
            row.archived = archived
        row.updated_at = now
        await self.db.flush()

    async def touch_conversation(self, conversation_id: str, now) -> None:
        result = await self.db.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        row = result.scalar_one_or_none()
        if row:
            row.updated_at = now
            await self.db.flush()

    async def delete_conversation(self, conversation_id: str) -> bool:
        result = await self.db.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self.db.delete(row)
        return True

    async def list_messages_by_conversation(self, conversation_id: str) -> list[ChatMessageRecord]:
        result = await self.db.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at)
        )
        return [self._to_message_record(row) for row in result.scalars().all()]

    async def create_message(
        self,
        message_id: str,
        conversation_id: str,
        role: str,
        content: str,
        created_at,
        agent: str | None = None,
    ) -> None:
        self.db.add(
            MessageModel(
                id=message_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                agent=agent,
                created_at=created_at,
            )
        )
        await self.db.flush()

    async def delete_messages_by_conversation(self, conversation_id: str) -> None:
        await self.db.execute(
            delete(MessageModel).where(MessageModel.conversation_id == conversation_id)
        )

    async def update_message_content(self, message_id: str, content: str) -> bool:
        result = await self.db.execute(select(MessageModel).where(MessageModel.id == message_id))
        row = result.scalar_one_or_none()
        if row is None:
            return False
        row.content = content
        await self.db.flush()
        return True

    async def get_agent_by_id(self, agent_id: str) -> ChatAgentRecord | None:
        result = await self.db.execute(
            select(AgentConfigModel).where(AgentConfigModel.id == agent_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return ChatAgentRecord(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            class_name=row.class_name,
            model_id=row.model_id,
            provider=row.provider,
        )

    async def list_agent_names_by_ids(self, agent_ids: set[str]) -> dict[str, str]:
        if not agent_ids:
            return {}
        result = await self.db.execute(
            select(AgentConfigModel).where(AgentConfigModel.id.in_(agent_ids))
        )
        return {row.id: row.name for row in result.scalars().all()}

    async def get_enabled_workspace_abi_server(
        self, workspace_id: str
    ) -> ChatInferenceServerRecord | None:
        result = await self.db.execute(
            select(InferenceServerModel)
            .where(InferenceServerModel.workspace_id == workspace_id)
            .where(InferenceServerModel.type == "abi")
            .where(InferenceServerModel.enabled)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return ChatInferenceServerRecord(
            id=row.id,
            workspace_id=row.workspace_id,
            name=row.name,
            type=row.type,
            endpoint=row.endpoint,
            api_key=row.api_key,
        )

    async def get_workspace_secret(self, workspace_id: str, key: str) -> ChatSecretRecord | None:
        result = await self.db.execute(
            select(SecretModel)
            .where(SecretModel.workspace_id == workspace_id)
            .where(SecretModel.key == key)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return ChatSecretRecord(encrypted_value=row.encrypted_value)
