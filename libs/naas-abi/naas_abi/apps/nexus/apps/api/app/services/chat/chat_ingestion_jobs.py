"""Chat file ingestion jobs: the record a job leaves, and the port that keeps them.

A job is created by the upload/ingest routes, then moved through its statuses by
the ingestion worker. Each write of the port is committed when it returns: the
worker may read a job as soon as the route has published it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


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


class ChatIngestionJobStorePort(ABC):
    @abstractmethod
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
        """Store a new job (``attempt`` 0, ``max_attempts`` 3) and return it."""

    @abstractmethod
    async def get_job_for_user(self, job_id: str, user_id: str) -> ChatIngestionJobRecord | None:
        """The job, if ``user_id`` started it."""

    @abstractmethod
    async def get_job(self, job_id: str) -> ChatIngestionJobRecord | None:
        """The job, whoever started it."""

    @abstractmethod
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
        """Set ``status`` and ``updated_at``, and every other field given (``None``
        leaves one as it is). ``started`` sets ``started_at`` once; ``finished``
        sets ``finished_at``; ``increment_attempt`` adds one to ``attempt``.
        Returns None for an unknown job."""
