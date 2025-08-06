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
    from src import services

    integration_configuration = YourIntegrationConfiguration()

    pipeline_configuration = YourPipelineConfiguration(
        integration_configuration=integration_configuration,
        triple_store=services.triple_store,
    )

    return YourPipeline(pipeline_configuration)

def test_pipeline_name(pipeline: YourPipeline):
    graph = pipeline.run(YourPipelineParameters(parameter_1="value1", parameter_2=42))

    assert graph is not None, graph

    for s, p, o in graph:
        assert s is not None, s
        assert p is not None, p
        assert o is not None, o