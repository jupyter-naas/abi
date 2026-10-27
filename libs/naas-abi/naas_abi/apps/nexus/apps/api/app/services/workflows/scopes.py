"""Which module scope a workflow is (core ``services/iam/module_scopes``).

A workflow and a pipeline are both jobs of kind ``workflow``; a pipeline's name
is ``pipeline.<slug>``. Each is ``workflow/<module>/<name>`` or
``pipeline/<module>/<name>`` of the ``module`` catalog: ``RunWorkflow`` /
``RunPipeline`` to list and start it in a workspace, ``ReadWorkflowRuns`` /
``ReadPipelineRuns`` to read one's own runs of it there.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi_core.services.iam.module_scopes import PIPELINE, RUNS_ACTION, WORKFLOW

PIPELINE_PREFIX = "pipeline."


def workflow_scope(module_id: str, name: str) -> ModuleScope:
    kind = PIPELINE if name.startswith(PIPELINE_PREFIX) else WORKFLOW
    return ModuleScope(kind, module_id, name)


def runs_action(scope: ModuleScope) -> str:
    """The action that reads one's own runs of ``scope``."""
    return RUNS_ACTION[scope.type]
