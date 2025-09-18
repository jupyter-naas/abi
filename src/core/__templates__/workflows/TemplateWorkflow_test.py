import pytest

from src.core.__templates__.workflows.TemplateWorkflow import (
    YourWorkflow, YourWorkflowConfiguration, YourWorkflowParameters
)

@pytest.fixture
def workflow() -> YourWorkflow:
    from src.core.__templates__.integrations.TemplateIntegration import (
        YourIntegrationConfiguration
    )

    integration_configuration = YourIntegrationConfiguration()

    workflow_configuration = YourWorkflowConfiguration(
        integration_config=integration_configuration
    )

    return YourWorkflow(workflow_configuration)

def test_workflow_name(workflow: YourWorkflow):
    result = workflow.run_workflow(YourWorkflowParameters(parameter_1="value1", parameter_2=42))

    assert result is not None, result
    assert "value1" in result, result