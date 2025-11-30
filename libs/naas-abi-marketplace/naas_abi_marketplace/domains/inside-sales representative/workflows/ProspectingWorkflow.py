"""
🚧 NOT FUNCTIONAL YET - Workflow Template
Remote prospecting and lead generation workflow
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from naas_abi_core import logger
from naas_abi_core.workflow.workflow import Workflow, WorkflowConfiguration


@dataclass
class ProspectingWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for ProspectingWorkflow"""

    pass


class ProspectingWorkflow(Workflow):
    """
    Remote prospecting and lead generation workflow

    NOT FUNCTIONAL YET - Template only
    """

    def __init__(self, config: Optional[ProspectingWorkflowConfiguration] = None):
        """Initialize ProspectingWorkflow - NOT FUNCTIONAL YET"""
        super().__init__(config or ProspectingWorkflowConfiguration())
        logger.warning("🚧 ProspectingWorkflow is not functional yet - template only")

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute workflow - NOT FUNCTIONAL YET"""
        logger.warning("🚧 ProspectingWorkflow.execute() not implemented yet")

        return {
            "status": "template_only",
            "message": "🚧 Workflow not functional yet",
            "inputs_received": list(inputs.keys()),
        }

    def get_workflow_description(self) -> str:
        """Get workflow description"""
        return "Remote prospecting and lead generation workflow"
