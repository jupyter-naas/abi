from __future__ import annotations

import asyncio

from .{{workflow_name_pascal}}Workflow import (
    {{workflow_name_pascal}}Workflow,
    {{workflow_name_pascal}}WorkflowConfiguration,
    {{workflow_name_pascal}}WorkflowParameters,
)


def test_the_workflow_runs() -> None:
    workflow = {{workflow_name_pascal}}Workflow({{workflow_name_pascal}}WorkflowConfiguration())

    result = asyncio.run(
        workflow.run({{workflow_name_pascal}}WorkflowParameters(message="hi"))
    )

    assert result == {"message": "hi"}


def test_the_workflow_is_named_after_its_class() -> None:
    assert {{workflow_name_pascal}}Workflow.slug() == "{{workflow_name_snake}}_workflow"
