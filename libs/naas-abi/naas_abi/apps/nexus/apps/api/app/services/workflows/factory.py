"""Wires the workflows service over the sysadmin jobs admin (same adapters, same audit log)."""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import get_jobs_admin
from naas_abi.apps.nexus.apps.api.app.services.workflows.service import WorkflowsService

_service: WorkflowsService | None = None


def get_workflows_service() -> Any:
    """FastAPI dependency: one per API process, built on first use."""
    global _service
    if _service is None:
        _service = WorkflowsService(get_jobs_admin())
    return _service
