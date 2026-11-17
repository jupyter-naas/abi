"""``ChatIngestionJobStorePort``: one contract, run against every adapter."""

from __future__ import annotations

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import (
    ConversationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.secondary.chat_ingestion_jobs_memory import (  # noqa: E501
    MemoryChatIngestionJobStore,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.secondary.chat_ingestion_jobs_sql import (  # noqa: E501
    SqlChatIngestionJobStore,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_ingestion_jobs import (
    ChatIngestionJobStorePort,
)


@pytest_asyncio.fixture(params=["sql", "memory"])
async def store(request: pytest.FixtureRequest, nexus_db) -> ChatIngestionJobStorePort:
    if request.param == "memory":
        return MemoryChatIngestionJobStore()
    async with nexus_db() as db:
        db.add(UserModel(id="u1", email="u1@example.com", name="U1"))
        db.add(WorkspaceModel(id="ws-1", name="WS", slug="ws", owner_id="u1"))
        db.add(ConversationModel(id="c1", workspace_id="ws-1", user_id="u1", title="C"))
        await db.commit()
    return SqlChatIngestionJobStore(nexus_db)


async def _create(store: ChatIngestionJobStorePort, job_id: str = "job-1"):
    return await store.create_job(
        job_id=job_id,
        conversation_id="c1",
        workspace_id="ws-1",
        user_id="u1",
        source_type="upload",
        source_path="my-drive/u1/uploads/a.pdf",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
    )


@pytest.mark.asyncio
async def test_a_new_job_is_queued_with_no_attempt(store) -> None:
    job = await _create(store)

    assert (job.id, job.status, job.attempt, job.max_attempts) == ("job-1", "queued", 0, 3)
    assert job.started_at is None and job.finished_at is None
    assert job.created_at is not None and job.updated_at is not None


@pytest.mark.asyncio
async def test_a_job_is_visible_to_its_user_only(store) -> None:
    await _create(store)

    assert (await store.get_job_for_user("job-1", "u1")) is not None
    assert await store.get_job_for_user("job-1", "u2") is None
    assert (await store.get_job("job-1")) is not None
    assert await store.get_job("job-404") is None


@pytest.mark.asyncio
async def test_update_status_sets_only_what_it_is_given(store) -> None:
    await _create(store)

    started = await store.update_status(
        "job-1", "hashing", progress=10, started=True, increment_attempt=True
    )
    assert started is not None
    assert (started.status, started.progress, started.attempt) == ("hashing", 10, 1)
    first_start = started.started_at
    assert first_start is not None

    done = await store.update_status(
        "job-1",
        "ready",
        progress=100,
        cache_hit=True,
        file_sha256="abc",
        collection_name="chat_c1",
        chunks_count=4,
        started=True,
        finished=True,
    )
    assert done is not None
    assert (done.status, done.cache_hit, done.chunks_count, done.collection_name) == (
        "ready",
        True,
        4,
        "chat_c1",
    )
    assert done.started_at == first_start and done.finished_at is not None
    assert done.attempt == 1

    stored = await store.get_job("job-1")
    assert stored is not None and stored.status == "ready" and stored.file_sha256 == "abc"


@pytest.mark.asyncio
async def test_updating_an_unknown_job_returns_none(store) -> None:
    assert await store.update_status("job-404", "failed") is None
