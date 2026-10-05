"""People process pipelines (Act of Working, Studying and Certification)."""

from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.ActOfCertificationPipeline import (
    ActOfCertificationPipeline,
    ActOfCertificationPipelineConfiguration,
    ActOfCertificationPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.ActOfStudyingPipeline import (
    ActOfStudyingPipeline,
    ActOfStudyingPipelineConfiguration,
    ActOfStudyingPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.ActOfWorkingPipeline import (
    ActOfWorkingPipeline,
    ActOfWorkingPipelineConfiguration,
    ActOfWorkingPipelineParameters,
)

__all__ = [
    "ActOfCertificationPipeline",
    "ActOfCertificationPipelineConfiguration",
    "ActOfCertificationPipelineParameters",
    "ActOfStudyingPipeline",
    "ActOfStudyingPipelineConfiguration",
    "ActOfStudyingPipelineParameters",
    "ActOfWorkingPipeline",
    "ActOfWorkingPipelineConfiguration",
    "ActOfWorkingPipelineParameters",
]
