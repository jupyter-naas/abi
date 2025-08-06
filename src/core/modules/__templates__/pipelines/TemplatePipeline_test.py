import pytest

from src.core.modules.__templates__.pipelines.TemplatePipeline import (
    YourPipeline, 
    YourPipelineConfiguration, 
    YourPipelineParameters,
)

@pytest.fixture
def pipeline() -> YourPipeline:
    from src.core.modules.__templates__.integrations.TemplateIntegration import (
        YourIntegrationConfiguration
    )

    integration_configuration = YourIntegrationConfiguration(
        attribute_1="value1",
        attribute_2=42
    )

    pipeline_configuration = YourPipelineConfiguration(
        integration_configuration=integration_configuration,
    )

    return YourPipeline(pipeline_configuration)

def test_pipeline_name(pipeline: YourPipeline):
    result = pipeline.run(YourPipelineParameters(parameter_1="value1", parameter_2=42))

    assert result is not None, result
    assert "value1" in result, result