"""
🚧 NOT FUNCTIONAL YET - Workflow Template
Treasury operations and compliance workflow
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from naas_abi_core import logger
from naas_abi_core.workflow.workflow import Workflow, WorkflowConfiguration


@dataclass
class TreasuryOperationsWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for TreasuryOperationsWorkflow"""

    pass


class TreasuryOperationsWorkflow(Workflow):
    """
    Treasury operations and compliance workflow

    NOT FUNCTIONAL YET - Template only
    """

    def __init__(
        self, config: Optional[TreasuryOperationsWorkflowConfiguration] = None
    ):
        """Initialize TreasuryOperationsWorkflow - NOT FUNCTIONAL YET"""
        super().__init__(config or TreasuryOperationsWorkflowConfiguration())
        logger.warning(
            "🚧 TreasuryOperationsWorkflow is not functional yet - template only"
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute workflow - NOT FUNCTIONAL YET"""
        logger.warning("🚧 TreasuryOperationsWorkflow.execute() not implemented yet")

        return {
            "status": "template_only",
            "message": "🚧 Workflow not functional yet",
            "inputs_received": list(inputs.keys()),
        }

    def get_workflow_description(self) -> str:
        """Get workflow description"""
        return "Treasury operations and compliance workflow"
