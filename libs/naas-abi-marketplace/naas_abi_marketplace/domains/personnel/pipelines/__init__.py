"""Personnel pipelines: what an organization records about its own staff."""

from naas_abi_marketplace.domains.personnel.pipelines.ActOfEmploymentPipeline import (
    ActOfEmploymentPipeline,
    ActOfEmploymentPipelineConfiguration,
    ActOfEmploymentPipelineParameters,
)
from naas_abi_marketplace.domains.personnel.pipelines.PersonnelProfilePipeline import (
    PersonnelProfilePipeline,
    PersonnelProfilePipelineConfiguration,
    PersonnelProfilePipelineParameters,
)

__all__ = [
    "ActOfEmploymentPipeline",
    "ActOfEmploymentPipelineConfiguration",
    "ActOfEmploymentPipelineParameters",
    "PersonnelProfilePipeline",
    "PersonnelProfilePipelineConfiguration",
    "PersonnelProfilePipelineParameters",
]
