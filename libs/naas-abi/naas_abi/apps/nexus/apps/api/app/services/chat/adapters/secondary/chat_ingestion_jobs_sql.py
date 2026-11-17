"""Chat ingestion jobs in the Nexus database's ``chat_ingestion_jobs`` table."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.core import database
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.models import ChatIngestionJobModel
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_ingestion_jobs import (
    ChatIngestionJobRecord,
    ChatIngestionJobStorePort,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SqlChatIngestionJobStore(ChatIngestionJobStorePort):
    """One session per call, committed before it returns. ``sessions`` defaults to
    the API's session factory, read when called."""

    def __init__(self, sessions: Callable[[], AsyncSession] | None = None) -> None:
        self._sessions = sessions

    def _session(self) -> AsyncSession:
        return (self._sessions or database.AsyncSessionLocal)()

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
        async with self._session() as db:
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return self._to_record(row)

    async def get_job_for_user(self, job_id: str, user_id: str) -> ChatIngestionJobRecord | None:
        async with self._session() as db:
            result = await db.execute(
                select(ChatIngestionJobModel)
                .where(ChatIngestionJobModel.id == job_id)
                .where(ChatIngestionJobModel.user_id == user_id)
            )
            row = result.scalar_one_or_none()
            return self._to_record(row) if row else None

    async def get_job(self, job_id: str) -> ChatIngestionJobRecord | None:
        async with self._session() as db:
            row = await db.get(ChatIngestionJobModel, job_id)
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
        async with self._session() as db:
            row = await db.get(ChatIngestionJobModel, job_id)
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

            await db.commit()
            return self._to_record(row)
