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
from sqlalchemy import case, delete, func, select
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
            module_path=model.module_path,
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
        self,
        workspace_id: str,
        user_id: str,
        limit: int,
        offset: int,
        module_path: str | None = None,
    ) -> list[ChatConversationRecord]:
        query = (
            select(ConversationModel)
            .where(ConversationModel.workspace_id == workspace_id)
            .where(ConversationModel.user_id == user_id)
        )
        if module_path is not None:
            query = query.where(ConversationModel.module_path == module_path)
        query = query.order_by(ConversationModel.updated_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return [self._to_conversation_record(row) for row in result.scalars().all()]

    async def create_conversation(
        self,
        conversation_id: str,
        workspace_id: str,
        user_id: str,
        title: str,
        agent: str,
        now,
        module_path: str | None = None,
    ) -> ChatConversationRecord:
        row = ConversationModel(
            id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            agent=agent,
            module_path=module_path,
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
        # Streaming writes the user row and the paired assistant row with the
        # same ``created_at``; without a deterministic tie-breaker the pair can
        # surface assistant-first. Order user < assistant < system on ties.
        role_order = case(
            (MessageModel.role == "user", 0),
            (MessageModel.role == "assistant", 1),
            else_=2,
        )
        result = await self.db.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at, role_order, MessageModel.id)
        )
        return [self._to_message_record(row) for row in result.scalars().all()]

    async def count_messages_for_conversations(
        self, conversation_ids: list[str]
    ) -> dict[str, int]:
        if not conversation_ids:
            return {}
        result = await self.db.execute(
            select(MessageModel.conversation_id, func.count(MessageModel.id))
            .where(MessageModel.conversation_id.in_(conversation_ids))
            .group_by(MessageModel.conversation_id)
        )
        counts = {cid: int(count) for cid, count in result.all()}
        # Conversations with zero rows must still appear in the map so callers
        # can render "0 messages" without falling back to "unknown".
        return {cid: counts.get(cid, 0) for cid in conversation_ids}

    async def list_messages_for_conversations(
        self, conversation_ids: list[str]
    ) -> dict[str, list[ChatMessageRecord]]:
        if not conversation_ids:
            return {}
        role_order = case(
            (MessageModel.role == "user", 0),
            (MessageModel.role == "assistant", 1),
            else_=2,
        )
        result = await self.db.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id.in_(conversation_ids))
            .order_by(MessageModel.conversation_id, MessageModel.created_at, role_order, MessageModel.id)
        )
        by_conv: dict[str, list[ChatMessageRecord]] = {cid: [] for cid in conversation_ids}
        for row in result.scalars().all():
            by_conv.setdefault(row.conversation_id, []).append(self._to_message_record(row))
        return by_conv

    async def list_conversations_by_ids(
        self, conversation_ids: list[str]
    ) -> dict[str, ChatConversationRecord]:
        if not conversation_ids:
            return {}
        result = await self.db.execute(
            select(ConversationModel).where(ConversationModel.id.in_(conversation_ids))
        )
        return {row.id: self._to_conversation_record(row) for row in result.scalars().all()}

    async def list_conversations_by_updated_at(
        self,
        date_start,
        date_end,
        workspace_id: str | None = None,
        limit: int = 500,
    ) -> list[ChatConversationRecord]:
        # Strip timezone so the values match the TIMESTAMP WITHOUT TIME ZONE column.
        start = date_start.replace(tzinfo=None) if hasattr(date_start, "tzinfo") else date_start
        end = date_end.replace(tzinfo=None) if hasattr(date_end, "tzinfo") else date_end
        q = (
            select(ConversationModel)
            .where(ConversationModel.updated_at >= start)
            .where(ConversationModel.updated_at <= end)
        )
        if workspace_id:
            q = q.where(ConversationModel.workspace_id == workspace_id)
        q = q.order_by(ConversationModel.updated_at.desc()).limit(limit)
        result = await self.db.execute(q)
        return [self._to_conversation_record(row) for row in result.scalars().all()]

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

    async def update_message_metadata(self, message_id: str, metadata: str) -> bool:
        result = await self.db.execute(select(MessageModel).where(MessageModel.id == message_id))
        row = result.scalar_one_or_none()
        if row is None:
            return False
        row.metadata_ = metadata
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
