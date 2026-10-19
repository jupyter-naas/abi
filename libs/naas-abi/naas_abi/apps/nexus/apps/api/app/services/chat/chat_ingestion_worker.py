from __future__ import annotations

import asyncio
import contextvars
import json
import logging
from dataclasses import replace
from typing import Any

from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_ingestion import (
    ChatFileIngestionError,
    ChatFileIngestionService,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_ingestion_jobs import (
    ChatIngestionJobService,
)
from naas_abi.apps.nexus.apps.api.app.services.websocket.service import WebSocketService

logger = logging.getLogger(__name__)

CHAT_INGESTION_TOPIC = "chat_ingestion"
CHAT_INGESTION_ROUTING_KEY = "chat.file.ingest"


def publish_chat_ingestion_job(payload: dict[str, Any]) -> None:
    from naas_abi import ABIModule

    module = ABIModule.get_instance()
    module.engine.services.bus.enqueue(
        CHAT_INGESTION_TOPIC,
        CHAT_INGESTION_ROUTING_KEY,
        json.dumps(payload).encode(),
    )


async def _as_uploader(payload: dict[str, Any]) -> None:
    """Run a queued job as the request that queued it ran: ``api`` on behalf
    of the user who uploaded the file, so the user bounds every kernel call
    (RFC §5.3). The queue's consumer thread has no caller of its own.

    A job that names no user runs as nobody, never as ``api`` alone: its
    kernel calls are denied, and the job records its failure as any other."""
    from naas_abi_core.engine.call_context import (
        ANONYMOUS,
        as_service_account,
        use_call_context,
        user,
    )

    user_id = str(payload.get("user_id") or "")
    if not user_id:
        logger.error("chat ingestion payload missing user_id: %s", payload.get("job_id"))
        with use_call_context(ANONYMOUS):
            await process_chat_ingestion_job(payload)
        return
    with as_service_account("api") as context:
        with use_call_context(replace(context, on_behalf_of=user(user_id))):
            await process_chat_ingestion_job(payload)


async def _emit_ingestion_event(workspace_id: str, payload: dict[str, Any]) -> None:
    try:
        websocket = WebSocketService()
        await websocket.broadcast_to_workspace(
            workspace_id=workspace_id,
            event="chat.ingestion.status",
            data=payload,
        )
    except Exception:
        logger.exception("Unable to emit chat ingestion websocket event")


async def process_chat_ingestion_job(payload: dict[str, Any]) -> None:
    from naas_abi import ABIModule

    job_id = str(payload.get("job_id") or "")
    if not job_id:
        logger.error("chat ingestion payload missing job_id")
        return

    # The upload endpoint now commits the job row before publishing, but as a
    # safety net (e.g. DB replication lag) we retry a few times before giving up.
    record = None
    for attempt in range(5):
        async with AsyncSessionLocal() as db:
            jobs = ChatIngestionJobService(db)
            record = await jobs.update_status(
                job_id,
                "hashing",
                progress=10,
                started=True,
                increment_attempt=True,
            )
            await db.commit()
        if record is not None:
            break
        logger.warning(
            "chat ingestion job not found yet (attempt %d/5): %s — retrying in 0.5 s",
            attempt + 1,
            job_id,
        )
        await asyncio.sleep(0.5)

    if record is None:
        logger.error("chat ingestion job not found after retries, giving up: %s", job_id)
        return

    await _emit_ingestion_event(
        record.workspace_id,
        {
            "job_id": job_id,
            "conversation_id": record.conversation_id,
            "status": "hashing",
            "progress": 10,
        },
    )

    try:
        module = ABIModule.get_instance()
        ingestion_service = ChatFileIngestionService(
            object_storage=module.engine.services.object_storage,
            vector_store=module.engine.services.vector_store,
            cache_service=module.engine.services.cache,
        )

        workspace_id_for_progress: str | None = None
        conversation_id_for_progress: str | None = None

        async with AsyncSessionLocal() as db:
            jobs = ChatIngestionJobService(db)
            mid = await jobs.update_status(job_id, "cache_lookup", progress=25)
            await db.commit()
            if mid:
                workspace_id_for_progress = mid.workspace_id
                conversation_id_for_progress = mid.conversation_id
                await _emit_ingestion_event(
                    mid.workspace_id,
                    {
                        "job_id": job_id,
                        "conversation_id": mid.conversation_id,
                        "status": "cache_lookup",
                        "progress": 25,
                    },
                )

        # Build a thread-safe progress callback so that the CPU/IO-bound
        # ingest_from_path (running in an executor thread) can push WebSocket
        # events back onto the event loop without blocking it.
        loop = asyncio.get_running_loop()

        def _on_progress(status: str, progress: int) -> None:
            if workspace_id_for_progress and conversation_id_for_progress:
                asyncio.run_coroutine_threadsafe(
                    _emit_ingestion_event(
                        workspace_id_for_progress,
                        {
                            "job_id": job_id,
                            "conversation_id": conversation_id_for_progress,
                            "status": status,
                            "progress": progress,
                        },
                    ),
                    loop,
                )

        # Run the heavy ingestion work in a thread so we don't block the
        # uvicorn event loop during PDF conversion and embedding calls.
        # In this job's context: the executor thread would otherwise have none.
        result = await loop.run_in_executor(
            None,
            contextvars.copy_context().run,
            lambda: ingestion_service.ingest_from_path(
                workspace_id=str(payload["workspace_id"]),
                user_id=str(payload["user_id"]),
                conversation_id=str(payload["conversation_id"]),
                source_path=str(payload["source_path"]),
                embedding_model=str(payload.get("embedding_model") or "text-embedding-3-small"),
                embedding_dimension=int(payload.get("embedding_dimension") or 1536),
                on_progress=_on_progress,
            ),
        )

        async with AsyncSessionLocal() as db:
            jobs = ChatIngestionJobService(db)
            done = await jobs.update_status(
                job_id,
                "ready",
                progress=100,
                cache_hit=result.cache_hit,
                file_sha256=result.file_sha256,
                collection_name=result.collection_name,
                chunks_count=result.chunks_count,
                finished=True,
            )
            await db.commit()

            if done:
                await _emit_ingestion_event(
                    done.workspace_id,
                    {
                        "job_id": job_id,
                        "conversation_id": done.conversation_id,
                        "status": "ready",
                        "progress": 100,
                        "cache_hit": done.cache_hit,
                        "chunks_count": done.chunks_count,
                    },
                )

    except ChatFileIngestionError as exc:
        async with AsyncSessionLocal() as db:
            jobs = ChatIngestionJobService(db)
            failed = await jobs.update_status(
                job_id,
                "failed",
                progress=100,
                error_code="INGESTION_ERROR",
                error_message=str(exc),
                finished=True,
            )
            await db.commit()
            if failed:
                await _emit_ingestion_event(
                    failed.workspace_id,
                    {
                        "job_id": job_id,
                        "conversation_id": failed.conversation_id,
                        "status": "failed",
                        "progress": 100,
                        "error": str(exc),
                    },
                )
    except Exception as exc:
        logger.exception("chat ingestion worker failed for job %s", job_id)
        async with AsyncSessionLocal() as db:
            jobs = ChatIngestionJobService(db)
            failed = await jobs.update_status(
                job_id,
                "failed",
                progress=100,
                error_code="UNEXPECTED_ERROR",
                error_message=str(exc),
                finished=True,
            )
            await db.commit()
            if failed:
                await _emit_ingestion_event(
                    failed.workspace_id,
                    {
                        "job_id": job_id,
                        "conversation_id": failed.conversation_id,
                        "status": "failed",
                        "progress": 100,
                        "error": str(exc),
                    },
                )


def start_chat_ingestion_consumer(app: FastAPI) -> None:
    if getattr(app.state, "chat_ingestion_consumer_started", False):
        return

    from naas_abi import ABIModule

    # Must be called from within a running event loop (e.g. a FastAPI startup
    # handler) so we can hand the existing loop to the consumer thread and
    # schedule coroutines on it instead of creating a second loop via
    # asyncio.run(), which would conflict with asyncpg connections bound to
    # the uvicorn loop.
    loop = asyncio.get_running_loop()

    module = ABIModule.get_instance()

    def _callback(body: bytes) -> None:
        payload = json.loads(body.decode())
        future = asyncio.run_coroutine_threadsafe(_as_uploader(payload), loop)
        future.result()  # block the pika thread until the job is done

    consumer_thread = module.engine.services.bus.dequeue(
        CHAT_INGESTION_TOPIC,
        CHAT_INGESTION_ROUTING_KEY,
        _callback,
    )
    app.state.chat_ingestion_consumer_thread = consumer_thread
    app.state.chat_ingestion_consumer_started = True
