import pytest

from src.marketplace.applications.linkedin.integrations.LinkedInExportIntegration import LinkedInExportIntegrationConfiguration
from src.marketplace.applications.linkedin.pipelines.LinkedInExportProfilePipeline import LinkedInExportProfilePipelineConfiguration
from src import services
from src.marketplace.applications.linkedin.pipelines.LinkedInExportConnectionsPipeline import (
    LinkedInExportConnectionsPipeline,
    LinkedInExportConnectionsPipelineConfiguration,
    LinkedInExportConnectionsPipelineParameters,
)

@pytest.fixture
def pipeline():
    limit = 1
    linkedin_export_integration_configuration = LinkedInExportIntegrationConfiguration(
        export_file_path="storage/datastore/linkedin/export/florent-ravenel/Complete_LinkedInDataExport_11-06-2025.zip (1).zip"
    )
    linkedin_export_profile_pipeline_configuration = LinkedInExportProfilePipelineConfiguration(
        triple_store=services.triple_store_service,
        linkedin_export_configuration=linkedin_export_integration_configuration
    )
    pipeline_configuration = LinkedInExportConnectionsPipelineConfiguration(
        triple_store=services.triple_store_service, 
        linkedin_export_configuration=linkedin_export_integration_configuration,
        linkedin_export_profile_pipeline_configuration=linkedin_export_profile_pipeline_configuration,
        limit=limit
    )
    return LinkedInExportConnectionsPipeline(pipeline_configuration)

def test_run(pipeline: LinkedInExportConnectionsPipeline):
    parameters = LinkedInExportConnectionsPipelineParameters(
        linkedin_public_url="https://www.linkedin.com/in/florent-ravenel/",
        file_name="Connections.csv"
    )
    graph = pipeline.run(parameters)
    assert graph is not None, graph.serialize(format="turtle")
    assert len(graph) > 0, len(graph)