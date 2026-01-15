import pytest
from naas_abi_marketplace.applications.linkedin.integrations.LinkedInExportIntegration import (
    LinkedInExportIntegrationConfiguration,
)
from naas_abi_marketplace.applications.linkedin.pipelines.LinkedInExportConnectionsPipeline import (
    LinkedInExportConnectionsPipeline,
    LinkedInExportConnectionsPipelineConfiguration,
    LinkedInExportConnectionsPipelineParameters,
)
from naas_abi_marketplace.applications.linkedin.pipelines.LinkedInExportProfilePipeline import (
    LinkedInExportProfilePipelineConfiguration,
)


@pytest.fixture
def pipeline():
    from naas_abi_marketplace.applications.linkedin import ABIModule

    module = ABIModule.get_instance()
    triple_store_service = module.engine.services.triple_store

    limit = 1
    linkedin_export_integration_configuration = LinkedInExportIntegrationConfiguration(
        export_file_path="storage/datastore/linkedin/export/florent-ravenel/Complete_LinkedInDataExport_11-06-2025.zip (1).zip"
    )
    linkedin_export_profile_pipeline_configuration = (
        LinkedInExportProfilePipelineConfiguration(
            triple_store=triple_store_service,
            linkedin_export_configuration=linkedin_export_integration_configuration,
        )
    )
    pipeline_configuration = LinkedInExportConnectionsPipelineConfiguration(
        triple_store=triple_store_service,
        linkedin_export_configuration=linkedin_export_integration_configuration,
        linkedin_export_profile_pipeline_configuration=linkedin_export_profile_pipeline_configuration,
        limit=limit,
    )
    return LinkedInExportConnectionsPipeline(pipeline_configuration)


def test_run(pipeline: LinkedInExportConnectionsPipeline):
    parameters = LinkedInExportConnectionsPipelineParameters(
        linkedin_public_url="https://www.linkedin.com/in/florent-ravenel/",
        file_name="Connections.csv",
    )
    graph = pipeline.run(parameters)
    assert graph is not None, graph.serialize(format="turtle")
    assert len(graph) > 0, len(graph)
