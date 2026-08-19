"""Personnel process pipelines (Act of Working, Act of Studying)."""

from naas_abi_marketplace.domains.personnel.pipelines.ActOfStudyingPipeline import (
    ActOfStudyingPipeline,
    ActOfStudyingPipelineConfiguration,
    ActOfStudyingPipelineParameters,
)
from naas_abi_marketplace.domains.personnel.pipelines.ActOfWorkingPipeline import (
    ActOfWorkingPipeline,
    ActOfWorkingPipelineConfiguration,
    ActOfWorkingPipelineParameters,
)

__all__ = [
    "ActOfStudyingPipeline",
    "ActOfStudyingPipelineConfiguration",
    "ActOfStudyingPipelineParameters",
    "ActOfWorkingPipeline",
    "ActOfWorkingPipelineConfiguration",
    "ActOfWorkingPipelineParameters",
]
