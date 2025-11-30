"""
🚧 NOT FUNCTIONAL YET - Workflow Template
Campaign budget allocation and management workflow
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from naas_abi_core import logger
from naas_abi_core.workflow.workflow import Workflow, WorkflowConfiguration


@dataclass
class BudgetManagementWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for BudgetManagementWorkflow"""

    pass


class BudgetManagementWorkflow(Workflow):
    """
    Campaign budget allocation and management workflow

    NOT FUNCTIONAL YET - Template only
    """

    def __init__(self, config: Optional[BudgetManagementWorkflowConfiguration] = None):
        """Initialize BudgetManagementWorkflow - NOT FUNCTIONAL YET"""
        super().__init__(config or BudgetManagementWorkflowConfiguration())
        logger.warning(
            "🚧 BudgetManagementWorkflow is not functional yet - template only"
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute workflow - NOT FUNCTIONAL YET"""
        logger.warning("🚧 BudgetManagementWorkflow.execute() not implemented yet")

        return {
            "status": "template_only",
            "message": "🚧 Workflow not functional yet",
            "inputs_received": list(inputs.keys()),
        }

    def get_workflow_description(self) -> str:
        """Get workflow description"""
        return "Campaign budget allocation and management workflow"
