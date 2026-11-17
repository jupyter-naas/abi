"""Which ``ChatIngestionJobStorePort`` the routes and the ingestion worker use.

A route takes it as a FastAPI dependency (``Depends(ingestion_job_store)``), which
tests override; the worker, which runs outside a request, calls it directly.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.secondary.chat_ingestion_jobs_sql import (  # noqa: E501
    SqlChatIngestionJobStore,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_ingestion_jobs import (
    ChatIngestionJobStorePort,
)

_store: ChatIngestionJobStorePort = SqlChatIngestionJobStore()


def ingestion_job_store() -> ChatIngestionJobStorePort:
    return _store


def configure_ingestion_job_store(store: ChatIngestionJobStorePort) -> ChatIngestionJobStorePort:
    """Use ``store`` from now on; returns the one it replaces."""
    global _store
    previous, _store = _store, store
    return previous
