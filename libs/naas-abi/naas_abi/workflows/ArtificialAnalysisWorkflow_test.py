import os
from pathlib import Path

import pytest
from naas_abi.workflows.ArtificialAnalysisWorkflow import (
    ArtificialAnalysisWorkflow,
    ArtificialAnalysisWorkflowConfiguration,
    ArtificialAnalysisWorkflowParameters,
)


@pytest.fixture
def workflow() -> ArtificialAnalysisWorkflow:
    api_key = os.getenv("AA_AI_API_KEY", "test_key")

    workflow_configuration = ArtificialAnalysisWorkflowConfiguration(
        api_key=api_key, base_url="https://artificialanalysis.ai/api/v2"
    )

    return ArtificialAnalysisWorkflow(workflow_configuration)


@pytest.mark.skipif(
    not os.getenv("AA_AI_API_KEY"), reason="AA_AI_API_KEY environment variable not set"
)
def test_workflow_fetch_llms_data(workflow: ArtificialAnalysisWorkflow):
    """Test fetching LLMs data from Artificial Analysis API."""
    result = workflow.run_workflow(
        ArtificialAnalysisWorkflowParameters(endpoint="llms", include_categories=False)
    )

    assert result is not None, result
    assert result["status"] == "success", result
    assert result["models_count"] > 0, result
    assert "output_file" in result, result
    assert "timestamp" in result, result

    # Verify file was created
    output_file = Path(result["output_file"])
    assert output_file.exists(), f"Output file {output_file} was not created"

    # Verify file contains valid JSON
    import json

    with open(output_file, "r") as f:
        data = json.load(f)
    assert "data" in data, "JSON file should contain 'data' field"
    assert "metadata" in data, "JSON file should contain 'metadata' field"


def test_workflow_as_tools(workflow: ArtificialAnalysisWorkflow):
    """Test that workflow can be converted to LangChain tools."""
    tools = workflow.as_tools()

    assert len(tools) == 1, f"Expected 1 tool, got {len(tools)}"
    assert tools[0].name == "artificial_analysis_data_fetch"
    assert "Artificial Analysis" in tools[0].description
