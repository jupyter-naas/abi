import pytest
from naas_abi import services
from naas_abi_marketplace.applications.linkedin.integrations.LinkedInExportIntegration import (
    LinkedInExportIntegrationConfiguration,
)
from naas_abi_marketplace.applications.linkedin.pipelines.LinkedInExportProfilePipeline import (
    LinkedInExportProfilePipeline,
    LinkedInExportProfilePipelineConfiguration,
    LinkedInExportProfilePipelineParameters,
)


@pytest.fixture
def pipeline():
    pipeline_configuration = LinkedInExportProfilePipelineConfiguration(
        triple_store=services.triple_store_service,
        linkedin_export_configuration=LinkedInExportIntegrationConfiguration(
            export_file_path="storage/datastore/linkedin/export/florent-ravenel/Complete_LinkedInDataExport_11-06-2025.zip (1).zip"
        ),
    )
    return LinkedInExportProfilePipeline(pipeline_configuration)


def test_run(pipeline: LinkedInExportProfilePipeline):
    parameters = LinkedInExportProfilePipelineParameters(
        linkedin_public_url="https://www.linkedin.com/in/florent-ravenel/",
        file_name="Profile.csv",
    )
    graph = pipeline.run(parameters)
    assert graph is not None, graph.serialize(format="turtle")
    assert len(graph) > 0, len(graph)
