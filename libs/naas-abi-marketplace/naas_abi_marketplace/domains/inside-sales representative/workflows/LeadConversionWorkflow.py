"""
🚧 NOT FUNCTIONAL YET - Workflow Template
Inbound lead qualification and conversion workflow
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from naas_abi_core import logger
from naas_abi_core.workflow.workflow import Workflow, WorkflowConfiguration


@dataclass
class LeadConversionWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for LeadConversionWorkflow"""

    pass


class LeadConversionWorkflow(Workflow):
    """
    Inbound lead qualification and conversion workflow

    NOT FUNCTIONAL YET - Template only
    """

    def __init__(self, config: Optional[LeadConversionWorkflowConfiguration] = None):
        """Initialize LeadConversionWorkflow - NOT FUNCTIONAL YET"""
        super().__init__(config or LeadConversionWorkflowConfiguration())
        logger.warning(
            "🚧 LeadConversionWorkflow is not functional yet - template only"
        )

    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute workflow - NOT FUNCTIONAL YET"""
        logger.warning("🚧 LeadConversionWorkflow.execute() not implemented yet")

        return {
            "status": "template_only",
            "message": "🚧 Workflow not functional yet",
            "inputs_received": list(inputs.keys()),
        }

    def get_workflow_description(self) -> str:
        """Get workflow description"""
        return "Inbound lead qualification and conversion workflow"
