"""The database's visibility, installed by the API at start."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.visibility import runtime
from naas_abi.apps.nexus.apps.api.app.services.visibility.service import WorkspaceVisibility
from naas_abi_core.services.iam.module_scopes import AGENT, APP, PIPELINE, WORKFLOW


def default_visibility() -> WorkspaceVisibility:
    """Apps from ``app_configs`` and the catalog seed, module agents from
    ``agent_configs``, workflows and pipelines from ``workflow_visibility``."""
    from naas_abi.apps.nexus.apps.api.app.services.agents.visibility import (
        default_reader as agents_reader,
    )
    from naas_abi.apps.nexus.apps.api.app.services.apps.visibility import (
        default_reader as apps_reader,
    )
    from naas_abi.apps.nexus.apps.api.app.services.workflows.factory import (
        get_workflow_visibility,
    )
    from naas_abi.apps.nexus.apps.api.app.services.workflows.visibility import (
        WorkflowsVisibility,
    )

    workflows = WorkflowsVisibility(get_workflow_visibility())
    return WorkspaceVisibility(
        {AGENT: agents_reader(), APP: apps_reader(), WORKFLOW: workflows, PIPELINE: workflows}
    )


def install() -> None:
    """Install the database's visibility, once (the API's start)."""
    if runtime.current() is None:
        runtime.configure(default_visibility())
