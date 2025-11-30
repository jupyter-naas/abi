import pytest
from naas_abi_marketplace.__demo__.workflows.ExecutePythonCodeWorkflow import (
    ExecutePythonCodeWorkflow,
    ExecutePythonCodeWorkflowConfiguration,
    ExecutePythonCodeWorkflowParameters,
)


@pytest.fixture
def workflow() -> ExecutePythonCodeWorkflow:
    return ExecutePythonCodeWorkflow(ExecutePythonCodeWorkflowConfiguration())


def test_print(workflow: ExecutePythonCodeWorkflow):
    result = workflow.execute_python_code(
        ExecutePythonCodeWorkflowParameters(code="print('Hello, world!')")
    )
    assert result == "Hello, world!", result
