"""Which workflows and pipelines a workspace turned off (``services/visibility``):
``workflow_visibility``; one never switched is on."""

from __future__ import annotations

from collections.abc import Sequence

from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.services.visibility.port import VisibilityReaderPort
from naas_abi.apps.nexus.apps.api.app.services.workflows.port import WorkflowVisibilityPort


class WorkflowsVisibility(VisibilityReaderPort):
    def __init__(self, store: WorkflowVisibilityPort) -> None:
        self._store = store

    async def hidden(self, workspace_id: str, scopes: Sequence[ModuleScope]) -> set[ModuleScope]:
        off = {
            ModuleScope(s.type, s.module_id, s.name)
            for s in await self._store.list_for(workspace_id)
            if not s.enabled
        }
        return {scope for scope in scopes if scope in off}
