"""Wires the workflows service over the sysadmin jobs admin (same adapters, same audit log)."""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import get_jobs_admin
from naas_abi.apps.nexus.apps.api.app.services.workflows.port import WorkflowVisibilityPort
from naas_abi.apps.nexus.apps.api.app.services.workflows.service import WorkflowsService

_service: WorkflowsService | None = None
_visibility: WorkflowVisibilityPort | None = None


def get_workflows_service() -> Any:
    """FastAPI dependency: one per API process, built on first use."""
    global _service
    if _service is None:
        from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
        from naas_abi.apps.nexus.apps.api.app.services.workflows.adapters.secondary.sql import (
            SqlRunOwners,
        )

        _service = WorkflowsService(get_jobs_admin(), owners=SqlRunOwners(AsyncSessionLocal))
    return _service


def get_workflow_visibility() -> WorkflowVisibilityPort:
    """FastAPI dependency: the workspaces' on and off of workflows and pipelines."""
    global _visibility
    if _visibility is None:
        from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
        from naas_abi.apps.nexus.apps.api.app.services.workflows.adapters.secondary.sql import (
            SqlWorkflowVisibility,
        )

        _visibility = SqlWorkflowVisibility(AsyncSessionLocal)
    return _visibility
