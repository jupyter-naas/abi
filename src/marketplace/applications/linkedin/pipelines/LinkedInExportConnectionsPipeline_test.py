import pytest

from src.marketplace.applications.linkedin.integrations.LinkedInExportIntegration import LinkedInExportIntegrationConfiguration
from src import services
from src.marketplace.applications.linkedin.pipelines.LinkedInExportConnectionsPipeline import (
    LinkedInExportConnectionsPipeline,
    LinkedInExportConnectionsPipelineConfiguration,
    LinkedInExportConnectionsPipelineParameters,
)

@pytest.fixture
def pipeline():
    pipeline_configuration = LinkedInExportConnectionsPipelineConfiguration(
        triple_store=services.triple_store_service, 
        linkedin_export_configuration=LinkedInExportIntegrationConfiguration(
            export_file_path="storage/datastore/linkedin/export/florent-ravenel/Complete_LinkedInDataExport_11-06-2025.zip (1).zip"
        )
    )
    return LinkedInExportConnectionsPipeline(pipeline_configuration)

def test_run(pipeline: LinkedInExportConnectionsPipeline):
    parameters = LinkedInExportConnectionsPipelineParameters(
        file_name="Connections.csv"
    )
    graph = pipeline.run(parameters)
    assert graph is not None, graph.serialize(format="turtle")
    assert len(graph) > 0, len(graph)