import os
from pathlib import Path

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


def test_python_code_workflow_keeps_the_parent_environment_out(
    workflow: ExecutePythonCodeWorkflow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PARENT_ONLY_SETTING", "parent-value")

    result = workflow.execute_python_code(
        ExecutePythonCodeWorkflowParameters(
            code="import os; print(os.environ.get('PARENT_ONLY_SETTING'))"
        )
    )

    assert result == "None", result


def test_python_code_workflow_keeps_the_parent_directory_out(
    workflow: ExecutePythonCodeWorkflow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = str(
        workflow.execute_python_code(
            ExecutePythonCodeWorkflowParameters(code="import os; print(os.getcwd())")
        )
    )

    assert Path(result).resolve() != tmp_path.resolve(), result
    assert not os.path.exists(result)  # its own directory, removed afterwards
