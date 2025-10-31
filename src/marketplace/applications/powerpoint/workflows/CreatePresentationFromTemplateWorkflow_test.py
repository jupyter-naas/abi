import pytest

from src import services, secret, config
from src.marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegrationConfiguration
)
from src.marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration
)
from src.marketplace.applications.powerpoint.pipelines.AddPowerPointPresentationPipeline import (
    AddPowerPointPresentationPipelineConfiguration,
)
from src.marketplace.applications.powerpoint.workflows.CreatePresentationFromTemplateWorkflow import (
    CreatePresentationFromTemplateWorkflow, 
    CreatePresentationFromTemplateWorkflowConfiguration, 
    CreatePresentationFromTemplateWorkflowParameters
)
TEMPLATE_PATH = "src/marketplace/applications/powerpoint/templates/TemplateNaasPPT.pptx"

@pytest.fixture
def workflow() -> CreatePresentationFromTemplateWorkflow:
    datastore_path = "datastore/powerpoint/presentations/test"
    triple_store_service = services.triple_store_service
    naas_configuration = NaasIntegrationConfiguration(
        api_key=secret.get("NAAS_API_KEY")
    )
    powerpoint_configuration = PowerPointIntegrationConfiguration(
        template_path=TEMPLATE_PATH
    )
    pipeline_configuration = AddPowerPointPresentationPipelineConfiguration(
        powerpoint_configuration=powerpoint_configuration,
        triple_store=triple_store_service
    )
    return CreatePresentationFromTemplateWorkflow(CreatePresentationFromTemplateWorkflowConfiguration(
        triple_store=triple_store_service,
        powerpoint_configuration=powerpoint_configuration,
        naas_configuration=naas_configuration,
        pipeline_configuration=pipeline_configuration,
        datastore_path=datastore_path,
        workspace_id=config.workspace_id,
        storage_name=config.storage_name
    ))

def test_workflow_name(workflow: CreatePresentationFromTemplateWorkflow):
    from src.utils.Storage import get_json
    import os

    json_file_path = "datastore/powerpoint/presentations/tests/presentation_data.json"
    presentation_data = get_json(os.path.dirname(json_file_path), os.path.basename(json_file_path))
    
    result = workflow.create_presentation(
        CreatePresentationFromTemplateWorkflowParameters(
            presentation_name=presentation_data["presentation_title"], 
            slides_data=presentation_data["slides_data"], 
            template_path=TEMPLATE_PATH
        )
    )
    assert result is not None, result
    assert result["presentation_name"] is not None, result
    assert result["storage_path"] is not None, result
    assert result["download_url"] is not None, result
    assert result["presentation_uri"] is not None, result
    assert result["template_uri"] is not None, result