import pytest

from src.core.modules.abi.pipelines.AIAgentOntologyDeploymentPipeline import (
    AIAgentOntologyDeploymentPipeline, 
    AIAgentOntologyDeploymentConfiguration, 
    AIAgentOntologyDeploymentParameters,
)

@pytest.fixture
def pipeline() -> AIAgentOntologyDeploymentPipeline:
    from src import services

    pipeline_configuration = AIAgentOntologyDeploymentConfiguration(
        triple_store=services.triple_store,
        source_datastore_path="storage/datastore/test/ai_agent_ontology_generation",
        target_modules_path="test_modules"
    )

    return AIAgentOntologyDeploymentPipeline(pipeline_configuration)

@pytest.fixture
def mock_ontology_files(tmp_path):
    """Create mock ontology files for testing."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    
    # Create test ontology files
    test_files = [
        "20250811T120000_ChatgptOntology.ttl",
        "20250811T120000_ClaudeOntology.ttl", 
        "20250811T130000_ChatgptOntology.ttl",
        "20250811T130000_GeminiOntology.ttl"
    ]
    
    for filename in test_files:
        test_file = source_dir / filename
        test_file.write_text(f"# Test ontology: {filename}")
    
    return source_dir

def test_pipeline_basic_deployment(pipeline: AIAgentOntologyDeploymentPipeline, mock_ontology_files, tmp_path):
    """Test basic deployment functionality."""
    
    # Setup test paths
    target_dir = tmp_path / "target"
    
    # Update configuration paths
    config = pipeline.get_configuration()
    config.source_datastore_path = str(mock_ontology_files)
    config.target_modules_path = str(target_dir)
    
    # Run deployment
    parameters = AIAgentOntologyDeploymentParameters(
        timestamp_filter="20250811T120000",
        overwrite_existing=True
    )
    graph = pipeline.run(parameters)

    assert graph is not None
    
    # Verify triples were added
    triples = list(graph)
    assert len(triples) > 0

def test_extract_agent_name_from_filename(pipeline: AIAgentOntologyDeploymentPipeline):
    """Test agent name extraction from filenames."""
    
    # Test valid filenames
    assert pipeline._extract_agent_name_from_filename("20250811T120000_ChatgptOntology.ttl") == "chatgpt"
    assert pipeline._extract_agent_name_from_filename("20250811T120000_ClaudeOntology.ttl") == "claude"
    assert pipeline._extract_agent_name_from_filename("20250811T120000_GeminiOntology.ttl") == "gemini"
    
    # Test invalid filenames
    assert pipeline._extract_agent_name_from_filename("invalid_file.ttl") is None
    assert pipeline._extract_agent_name_from_filename("20250811T120000_InvalidFormat.txt") is None

def test_list_available_deployments(pipeline: AIAgentOntologyDeploymentPipeline, mock_ontology_files):
    """Test listing available deployments."""
    
    # Update configuration
    config = pipeline.get_configuration()
    config.source_datastore_path = str(mock_ontology_files)
    
    deployments = pipeline.list_available_deployments()
    
    assert "20250811T120000" in deployments
    assert "20250811T130000" in deployments
    assert "chatgpt" in deployments["20250811T120000"]
    assert "claude" in deployments["20250811T120000"]
