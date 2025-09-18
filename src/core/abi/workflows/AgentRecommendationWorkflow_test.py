import pytest
from unittest.mock import Mock, patch

from src.core.abi.workflows.AgentRecommendationWorkflow import (
    AgentRecommendationWorkflow, 
    AgentRecommendationConfiguration, 
    AgentRecommendationParameters,
)

@pytest.fixture
def workflow() -> AgentRecommendationWorkflow:
    """Create a test workflow instance."""
    mock_triple_store = Mock()
    
    workflow_configuration = AgentRecommendationConfiguration(
        triple_store=mock_triple_store,
        oxigraph_url="http://localhost:7878",
        queries_file_path="src/core/modules/abi/ontologies/application-level/AgentRecommendationSparqlQueries.ttl"
    )
    
    return AgentRecommendationWorkflow(workflow_configuration)

@pytest.fixture
def sample_parameters() -> AgentRecommendationParameters:
    """Create sample workflow parameters."""
    return AgentRecommendationParameters(
        intent_description="I want to create a business proposal",
        min_intelligence_score=75,
        max_input_cost=5.0,
        max_results=5
    )

def test_workflow_initialization(workflow):
    """Test that workflow initializes correctly and loads queries."""
    assert workflow is not None
    assert hasattr(workflow, '_queries')
    # Note: This will fail if the TTL file doesn't exist, which is expected

def test_intent_matching(workflow):
    """Test intent matching to appropriate queries."""
    # Test business proposal matching
    business_query = workflow._match_intent_to_query("I need to create a business proposal")
    assert "business" in business_query["intent_description"].lower()
    
    # Test coding matching  
    coding_query = workflow._match_intent_to_query("I want to write some Python code")
    assert "coding" in coding_query["intent_description"].lower()

def test_template_replacement(workflow):
    """Test SPARQL template variable replacement."""
    template = "SELECT * WHERE { ?x :score ?score . FILTER(?score >= {{ min_intelligence_score }}) } LIMIT {{ max_results }}"
    parameters = AgentRecommendationParameters(
        intent_description="test",
        min_intelligence_score=80,
        max_results=10
    )
    
    templated = workflow._template_query({"sparql_template": template}, parameters)
    assert "80" in templated
    assert "10" in templated
    assert "{{" not in templated

def test_conditional_blocks(workflow):
    """Test handling of conditional template blocks."""
    template = """
    SELECT * WHERE {
        ?x :hasProperty ?y .
        {% if max_input_cost %}
        FILTER(?cost <= {{ max_input_cost }})
        {% endif %}
    }
    """
    
    # Test with conditional parameter
    replacements = {"max_input_cost": 5.0}
    result = workflow._handle_conditional_blocks(template, replacements)
    assert "FILTER(?cost" in result
    
    # Test without conditional parameter
    replacements = {}
    result = workflow._handle_conditional_blocks(template, replacements)
    assert "FILTER(?cost" not in result

@patch('requests.post')
def test_sparql_execution(mock_post, workflow):
    """Test SPARQL query execution."""
    # Mock successful response
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "results": {
            "bindings": [
                {
                    "agent": {"value": "Claude AI Agent"},
                    "provider": {"value": "Anthropic"},
                    "inputCost": {"value": "8.0"},
                    "intelligenceIndex": {"value": "85"}
                }
            ]
        }
    }
    mock_post.return_value = mock_response
    
    results = workflow._execute_sparql_query("SELECT * WHERE { ?s ?p ?o }")
    
    assert len(results) == 1
    assert results[0]["agent"]["value"] == "Claude AI Agent"
    mock_post.assert_called_once()

def test_recommendation_formatting(workflow):
    """Test formatting of SPARQL results into recommendations."""
    raw_results = [
        {
            "agentLabel": {"value": "Claude AI Agent"},
            "provider": {"value": "Anthropic"},
            "inputCost": {"value": "8.0"},
            "outputCost": {"value": "24.0"},
            "intelligenceIndex": {"value": "85"}
        }
    ]
    
    parameters = AgentRecommendationParameters(
        intent_description="create a business proposal"
    )
    
    recommendations = workflow._format_recommendations(raw_results, parameters)
    
    assert len(recommendations) == 1
    recommendation = recommendations[0]
    
    assert recommendation["agent"] == "Claude AI Agent"
    assert recommendation["provider"] == "Anthropic"
    assert recommendation["costs"]["input_per_million_tokens"] == 8.0
    assert recommendation["performance"]["intelligence_index"] == 85.0
    assert "business proposal" in recommendation["recommendation_reason"]

def test_as_tools_returns_valid_tools(workflow):
    """Test that workflow returns valid LangChain tools."""
    tools = workflow.as_tools()
    
    assert len(tools) == 1
    tool = tools[0]
    
    assert tool.name == "recommend_ai_agents"
    assert "AI agents" in tool.description
    assert hasattr(tool, 'func')
    assert hasattr(tool, 'args_schema')

if __name__ == "__main__":
    pytest.main([__file__])
