from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.models import ChatIngestionJobModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class ChatIngestionJobRecord:
    id: str
    conversation_id: str
    workspace_id: str
    user_id: str
    source_type: str
    source_path: str
    embedding_model: str
    embedding_dimension: int
    status: str
    progress: int | None
    cache_hit: bool | None
    file_sha256: str | None
    collection_name: str | None
    chunks_count: int | None
    error_code: str | None
    error_message: str | None
    attempt: int
    max_attempts: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ChatIngestionJobService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _to_record(model: ChatIngestionJobModel) -> ChatIngestionJobRecord:
        return ChatIngestionJobRecord(
            id=model.id,
            conversation_id=model.conversation_id,
            workspace_id=model.workspace_id,
            user_id=model.user_id,
            source_type=model.source_type,
            source_path=model.source_path,
            embedding_model=model.embedding_model,
            embedding_dimension=model.embedding_dimension,
            status=model.status,
            progress=model.progress,
            cache_hit=model.cache_hit,
            file_sha256=model.file_sha256,
            collection_name=model.collection_name,
            chunks_count=model.chunks_count,
            error_code=model.error_code,
            error_message=model.error_message,
            attempt=model.attempt,
            max_attempts=model.max_attempts,
            created_at=model.created_at,
            updated_at=model.updated_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
        )

    async def create_job(
        self,
        job_id: str,
        conversation_id: str,
        workspace_id: str,
        user_id: str,
        source_type: str,
        source_path: str,
        embedding_model: str,
        embedding_dimension: int,
        status: str = "queued",
    ) -> ChatIngestionJobRecord:
        row = ChatIngestionJobModel(
            id=job_id,
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            source_type=source_type,
            source_path=source_path,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            status=status,
        )
        self.db.add(row)
        await self.db.flush()
        return self._to_record(row)

    async def get_job_for_user(self, job_id: str, user_id: str) -> ChatIngestionJobRecord | None:
        result = await self.db.execute(
            select(ChatIngestionJobModel)
            .where(ChatIngestionJobModel.id == job_id)
            .where(ChatIngestionJobModel.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def get_job(self, job_id: str) -> ChatIngestionJobRecord | None:
        result = await self.db.execute(
            select(ChatIngestionJobModel).where(ChatIngestionJobModel.id == job_id)
        )
        row = result.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def update_status(
        self,
        job_id: str,
        status: str,
        *,
        progress: int | None = None,
        cache_hit: bool | None = None,
        file_sha256: str | None = None,
        collection_name: str | None = None,
        chunks_count: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        started: bool = False,
        finished: bool = False,
        increment_attempt: bool = False,
    ) -> ChatIngestionJobRecord | None:
        result = await self.db.execute(
            select(ChatIngestionJobModel).where(ChatIngestionJobModel.id == job_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None

        now = _utc_now_naive()
        row.status = status
        row.updated_at = now
        if progress is not None:
            row.progress = progress
        if cache_hit is not None:
            row.cache_hit = cache_hit
        if file_sha256 is not None:
            row.file_sha256 = file_sha256
        if collection_name is not None:
            row.collection_name = collection_name
        if chunks_count is not None:
            row.chunks_count = chunks_count
        if error_code is not None:
            row.error_code = error_code
        if error_message is not None:
            row.error_message = error_message
        if started and row.started_at is None:
            row.started_at = now
        if finished:
            row.finished_at = now
        if increment_attempt:
            row.attempt += 1

        await self.db.flush()
        return self._to_record(row)
