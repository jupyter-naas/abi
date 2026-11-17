"""Chat ingestion jobs in process memory (tests)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_ingestion_jobs import (
    ChatIngestionJobRecord,
    ChatIngestionJobStorePort,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class MemoryChatIngestionJobStore(ChatIngestionJobStorePort):
    def __init__(self) -> None:
        self.jobs: dict[str, ChatIngestionJobRecord] = {}

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
        if job_id in self.jobs:
            raise ValueError(f"Job {job_id} already exists")
        now = _now()
        job = ChatIngestionJobRecord(
            id=job_id,
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            source_type=source_type,
            source_path=source_path,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
            status=status,
            progress=None,
            cache_hit=None,
            file_sha256=None,
            collection_name=None,
            chunks_count=None,
            error_code=None,
            error_message=None,
            attempt=0,
            max_attempts=3,
            created_at=now,
            updated_at=now,
            started_at=None,
            finished_at=None,
        )
        self.jobs[job_id] = job
        return replace(job)

    async def get_job_for_user(self, job_id: str, user_id: str) -> ChatIngestionJobRecord | None:
        job = self.jobs.get(job_id)
        return replace(job) if job is not None and job.user_id == user_id else None

    async def get_job(self, job_id: str) -> ChatIngestionJobRecord | None:
        job = self.jobs.get(job_id)
        return replace(job) if job is not None else None

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
        job = self.jobs.get(job_id)
        if job is None:
            return None
        now = _now()
        given = {
            "progress": progress,
            "cache_hit": cache_hit,
            "file_sha256": file_sha256,
            "collection_name": collection_name,
            "chunks_count": chunks_count,
            "error_code": error_code,
            "error_message": error_message,
        }
        changes: dict[str, object] = {k: v for k, v in given.items() if v is not None}
        changes["status"] = status
        changes["updated_at"] = now
        if started and job.started_at is None:
            changes["started_at"] = now
        if finished:
            changes["finished_at"] = now
        if increment_attempt:
            changes["attempt"] = job.attempt + 1
        job = replace(job, **changes)  # type: ignore[arg-type]
        self.jobs[job_id] = job
        return replace(job)
