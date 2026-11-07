"""A queued chat ingestion job runs for the user who uploaded the file."""

from __future__ import annotations

import asyncio

from naas_abi.apps.nexus.apps.api.app.services.chat import chat_ingestion_worker
from naas_abi_core.engine.call_context import ANONYMOUS, current_call_context, service_account, user


def test_a_job_runs_as_api_on_behalf_of_its_uploader(monkeypatch):
    seen = []

    async def process(payload):
        seen.append(current_call_context())

    monkeypatch.setattr(chat_ingestion_worker, "process_chat_ingestion_job", process)
    asyncio.run(chat_ingestion_worker._as_uploader({"user_id": "u-42"}))

    (context,) = seen
    assert context.principal == service_account("api")
    assert context.on_behalf_of == user("u-42")


def test_a_job_naming_no_user_runs_as_nobody_and_still_reaches_its_handling(monkeypatch):
    """Not a KeyError before the job's own error handling, which would leave
    it queued; not api alone, which would widen the job."""
    seen = []

    async def process(payload):
        seen.append(current_call_context())

    monkeypatch.setattr(chat_ingestion_worker, "process_chat_ingestion_job", process)
    asyncio.run(chat_ingestion_worker._as_uploader({"job_id": "j-1"}))

    (context,) = seen
    assert context.principal == ANONYMOUS.principal
    assert context.on_behalf_of is None
