import json

import pytest
from naas_abi.pipelines.AIAgentOntologyGenerationPipeline import (
    AIAgentOntologyGenerationConfiguration,
    AIAgentOntologyGenerationParameters,
    AIAgentOntologyGenerationPipeline,
)


@pytest.fixture
def pipeline() -> AIAgentOntologyGenerationPipeline:
    from naas_abi import services

    pipeline_configuration = AIAgentOntologyGenerationConfiguration(
        triple_store=services.triple_store,
        datastore_path="storage/datastore/test/ai_agent_ontology_generation",
        source_datastore_path="storage/datastore/test/artificial_analysis_workflow",
    )

    return AIAgentOntologyGenerationPipeline(pipeline_configuration)


@pytest.fixture
def mock_aa_data():
    """Mock Artificial Analysis data for testing."""
    return {
        "llms": [
            {
                "name": "GPT-4o",
                "slug": "gpt-4o",
                "model_creator": {"name": "OpenAI", "slug": "openai"},
                "pricing": {
                    "input_cost": 5.0,
                    "output_cost": 15.0,
                    "blended_cost": 10.0,
                },
                "performance": {
                    "output_speed": 25.5,
                    "time_to_first_token": 0.5,
                    "time_to_first_answer_token": 1.2,
                },
                "evaluations": {"index": 85, "coding_index": 90, "math_index": 80},
            },
            {
                "name": "Claude 3.5 Sonnet",
                "slug": "claude-35-sonnet",
                "model_creator": {"name": "Anthropic", "slug": "anthropic"},
                "pricing": {
                    "input_cost": 3.0,
                    "output_cost": 15.0,
                    "blended_cost": 9.0,
                },
                "performance": {
                    "output_speed": 22.1,
                    "time_to_first_token": 0.8,
                    "time_to_first_answer_token": 1.5,
                },
                "evaluations": {"index": 88, "coding_index": 85, "math_index": 82},
            },
        ]
    }


def test_pipeline_basic_functionality(
    pipeline: AIAgentOntologyGenerationPipeline, mock_aa_data, tmp_path
):
    """Test basic pipeline functionality with mock data."""

    # Setup test paths
    source_path = tmp_path / "source"
    source_path.mkdir()
    output_path = tmp_path / "output"

    # Create mock data file
    mock_file = source_path / "20250811T120000_llms_data.json"
    with open(mock_file, "w") as f:
        json.dump(mock_aa_data, f)

    # Update configuration paths
    config = pipeline.get_configuration()
    config.source_datastore_path = str(source_path)
    config.datastore_path = str(output_path)

    # Run pipeline
    parameters = AIAgentOntologyGenerationParameters(force_regenerate=True)
    graph = pipeline.run(parameters)

    assert graph is not None

    # Verify triples were added
    triples = list(graph)
    assert len(triples) > 0

    for s, p, o in triples:
        assert s is not None
        assert p is not None
        assert o is not None


def test_model_mapping_logic(pipeline: AIAgentOntologyGenerationPipeline):
    """Test the model to agent mapping logic."""

    # Test GPT model mapping
    gpt_model = {
        "name": "GPT-4o",
        "slug": "gpt-4o",
        "model_creator": {"name": "OpenAI"},
    }
    assert pipeline._determine_ai_agent_module(gpt_model) == "chatgpt"

    # Test Claude model mapping
    claude_model = {
        "name": "Claude 3.5 Sonnet",
        "slug": "claude-35-sonnet",
        "model_creator": {"name": "Anthropic"},
    }
    assert pipeline._determine_ai_agent_module(claude_model) == "claude"

    # Test Gemini vs Gemma mapping
    gemini_model = {
        "name": "Gemini 2.0",
        "slug": "gemini-2-0",
        "model_creator": {"name": "Google"},
    }
    assert pipeline._determine_ai_agent_module(gemini_model) == "gemini"

    gemma_model = {
        "name": "Gemma 3 27B",
        "slug": "gemma-3-27b",
        "model_creator": {"name": "Google"},
    }
    assert pipeline._determine_ai_agent_module(gemma_model) == "gemma"
