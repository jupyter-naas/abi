import pytest
from naas_abi import services
from naas_abi_marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegrationConfiguration,
)
from naas_abi_marketplace.applications.powerpoint.pipelines.AddPowerPointPresentationPipeline import (
    AddPowerPointPresentationPipeline,
    AddPowerPointPresentationPipelineConfiguration,
    AddPowerPointPresentationPipelineParameters,
)


@pytest.fixture
def pipeline() -> AddPowerPointPresentationPipeline:
    powerpoint_configuration = PowerPointIntegrationConfiguration(
        template_path="src/marketplace/applications/powerpoint/templates/TemplateSlides.pptx"
    )
    return AddPowerPointPresentationPipeline(
        AddPowerPointPresentationPipelineConfiguration(
            powerpoint_configuration=powerpoint_configuration,
            triple_store=services.triple_store_service,
        )
    )


def add_template_presentation(pipeline: AddPowerPointPresentationPipeline):
    pipeline.run(
        AddPowerPointPresentationPipelineParameters(
            presentation_name="Test Presentation",
            storage_path="src/marketplace/applications/powerpoint/templates/TemplateNaasPPT.pptx",
        )
    )
