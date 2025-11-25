import pytest

from src import services
from src.marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegrationConfiguration,
)
from src.marketplace.applications.powerpoint.pipelines.AddPowerPointPresentationPipeline import (
    AddPowerPointPresentationPipelineConfiguration,
    AddPowerPointPresentationPipelineParameters,
    AddPowerPointPresentationPipeline
)

@pytest.fixture
def pipeline() -> AddPowerPointPresentationPipeline:
    powerpoint_configuration = PowerPointIntegrationConfiguration(template_path="src/marketplace/applications/powerpoint/templates/TemplateSlides.pptx")
    return AddPowerPointPresentationPipeline(
        AddPowerPointPresentationPipelineConfiguration(
            powerpoint_configuration=powerpoint_configuration,
            triple_store=services.triple_store_service
        )
    )

def add_template_presentation(pipeline: AddPowerPointPresentationPipeline):
    pipeline.run(AddPowerPointPresentationPipelineParameters(
        presentation_name="Test Presentation",
        storage_path="src/marketplace/applications/powerpoint/templates/TemplateNaasPPT.pptx"
    ))