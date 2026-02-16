import pytest
from naas_abi_marketplace.applications.powerpoint import ABIModule
from naas_abi_marketplace.applications.naas.integrations.NaasIntegration import (
    NaasIntegrationConfiguration,
)
from naas_abi_marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegrationConfiguration,
)
from naas_abi_marketplace.applications.powerpoint.pipelines.AddPowerPointPresentationPipeline import (
    AddPowerPointPresentationPipelineConfiguration,
)
from naas_abi_marketplace.applications.powerpoint.workflows.CreatePresentationFromTemplateWorkflow import (
    CreatePresentationFromTemplateWorkflow,
    CreatePresentationFromTemplateWorkflowConfiguration,
    CreatePresentationFromTemplateWorkflowParameters,
)

TEMPLATE_PATH = "src/marketplace/applications/powerpoint/templates/TemplateNaasPPT.pptx"


@pytest.fixture
def workflow() -> CreatePresentationFromTemplateWorkflow:
    from naas_abi_core.engine.Engine import Engine

    # We need to load the engine to load the module.
    engine = Engine()
    engine.load(
        module_names=[
            "naas_abi_marketplace.applications.powerpoint",
            "naas_abi_marketplace.applications.naas",
        ]
    )

    module = ABIModule.get_instance()
    triple_store_service = module.engine.services.triple_store
    naas_configuration = NaasIntegrationConfiguration(
        api_key=module.engine.services.secret.get("NAAS_API_KEY") or ""
    )
    powerpoint_configuration = PowerPointIntegrationConfiguration(
        template_path=TEMPLATE_PATH
    )
    pipeline_configuration = AddPowerPointPresentationPipelineConfiguration(
        powerpoint_configuration=powerpoint_configuration,
        triple_store=triple_store_service,
    )
    return CreatePresentationFromTemplateWorkflow(
        CreatePresentationFromTemplateWorkflowConfiguration(
            triple_store=triple_store_service,
            powerpoint_configuration=powerpoint_configuration,
            naas_configuration=naas_configuration,
            pipeline_configuration=pipeline_configuration,
            datastore_path="datastore/powerpoint/presentations/test",
            workspace_id=module.configuration.workspace_id,
            storage_name=module.configuration.storage_name,
        )
    )


def test_workflow_name(workflow: CreatePresentationFromTemplateWorkflow):
    import os

    from naas_abi_core.utils.StorageUtils import StorageUtils
    from naas_abi_marketplace.applications.powerpoint import ABIModule

    json_file_path = "datastore/powerpoint/presentations/tests/presentation_data.json"
    storage_utils = StorageUtils(
        ABIModule.get_instance().engine.services.object_storage
    )
    presentation_data = storage_utils.get_json(
        os.path.dirname(json_file_path), os.path.basename(json_file_path)
    )

    result = workflow.create_presentation(
        CreatePresentationFromTemplateWorkflowParameters(
            presentation_name=presentation_data["presentation_title"],
            slides_data=presentation_data["slides_data"],
            template_path=TEMPLATE_PATH,
        )
    )
    assert result is not None, result
    assert result["presentation_name"] is not None, result
    assert result["storage_path"] is not None, result
    assert result["download_url"] is not None, result
    assert result["presentation_uri"] is not None, result
    assert result["template_uri"] is not None, result
