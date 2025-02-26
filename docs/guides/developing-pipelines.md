# Developing Pipelines

This guide walks you through the process of developing data processing pipelines in the ABI framework to extract, transform, and load data into the ontology store.

## Prerequisites

Before developing a pipeline, you should have:

- A working ABI installation
- Understanding of the [ABI architecture](../concepts/architecture.md)
- Familiarity with the [pipeline concept](../concepts/pipelines.md)
- Knowledge of the [ontology](../concepts/ontology.md) structure
- Access to relevant [integrations](../concepts/integrations.md)

## Pipeline Structure

A typical ABI pipeline consists of these components:

1. **Configuration Class**: Defines parameters for pipeline behavior and dependencies
2. **Parameters Class**: Defines runtime parameters for pipeline execution
3. **Pipeline Class**: Implements the ETL logic using integrations
4. **Graph Builder**: Creates and populates the knowledge graph
5. **API Interface**: Exposes the pipeline via API endpoints

## Steps to Develop a Pipeline

### 1. Define the Pipeline Configuration

Create a configuration class that extends `PipelineConfiguration`:

```python
from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from src.integrations import GithubIntegration
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService

@dataclass
class GithubRepositoryPipelineConfiguration(PipelineConfiguration):
    """Configuration for GitHub Repository Pipeline.
    
    Attributes:
        github_integration (GithubIntegration): The GitHub integration to use
        ontology_store (IOntologyStoreService): The ontology store service
        ontology_store_name (str): Name of the ontology store to use
    """
    github_integration: GithubIntegration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "github_data"
```

### 2. Define the Pipeline Parameters

Create a parameters class that extends `PipelineParameters`:

```python
from pydantic import BaseModel
from typing import List, Optional

class GithubRepositoryPipelineParameters(PipelineParameters):
    """Parameters for GitHub Repository Pipeline execution.
    
    Attributes:
        repository (str): GitHub repository in format "owner/repo"
        include_issues (bool): Whether to include repository issues
        include_pull_requests (bool): Whether to include pull requests
        include_contributors (bool): Whether to include repository contributors
        max_items (int): Maximum number of items to process per category
    """
    repository: str
    include_issues: bool = True
    include_pull_requests: bool = True
    include_contributors: bool = True
    max_items: int = 100
```

### 3. Implement the Pipeline Class

Create the main pipeline class that extends the `Pipeline` base class:

```python
from abi.utils.Graph import ABIGraph
from rdflib import Graph
from typing import Dict, List, Any

class GithubRepositoryPipeline(Pipeline):
    """Pipeline for extracting GitHub repository data and loading it into the ontology store."""
    
    __configuration: GithubRepositoryPipelineConfiguration
    
    def __init__(self, configuration: GithubRepositoryPipelineConfiguration):
        self.__configuration = configuration
        
    def run(self, parameters: GithubRepositoryPipelineParameters) -> Graph:
        """Run the pipeline to extract and process GitHub repository data.
        
        Args:
            parameters: Pipeline parameters
            
        Returns:
            Graph containing repository data
        """
        # Create a new graph for this run
        graph = ABIGraph()
        
        # Extract repository data
        owner, repo = parameters.repository.split('/')
        repo_data = self.__configuration.github_integration.get_repository(owner, repo)
        
        # Transform repository data into graph entities
        repository_uri = self._transform_repository(graph, repo_data)
        
        # Process additional data based on parameters
        if parameters.include_issues:
            issues = self.__configuration.github_integration.get_issues(
                owner, 
                repo, 
                max_results=parameters.max_items
            )
            self._transform_issues(graph, issues, repository_uri)
            
        if parameters.include_pull_requests:
            prs = self.__configuration.github_integration.get_pull_requests(
                owner, 
                repo, 
                max_results=parameters.max_items
            )
            self._transform_pull_requests(graph, prs, repository_uri)
            
        if parameters.include_contributors:
            contributors = self.__configuration.github_integration.get_contributors(
                owner, 
                repo, 
                max_results=parameters.max_items
            )
            self._transform_contributors(graph, contributors, repository_uri)
            
        # Store the graph in the ontology store
        self.__configuration.ontology_store.insert(
            self.__configuration.ontology_store_name,
            graph
        )
        
        return graph
```

### 4. Implement Data Transformation Methods

Add methods to transform external data into semantic graph entities:

```python
def _transform_repository(self, graph: ABIGraph, repo_data: Dict) -> str:
    """Transform repository data into graph entities.
    
    Args:
        graph: The graph to add entities to
        repo_data: Repository data from GitHub
        
    Returns:
        str: URI of the created repository entity
    """
    # Create a repository entity
    repo_uri = graph.create_entity(
        "Repository",
        {
            "id": str(repo_data["id"]),
            "name": repo_data["name"],
            "full_name": repo_data["full_name"],
            "description": repo_data.get("description", ""),
            "url": repo_data["html_url"],
            "stars": repo_data["stargazers_count"],
            "forks": repo_data["forks_count"],
            "created_at": repo_data["created_at"],
            "updated_at": repo_data["updated_at"]
        }
    )
    
    # Create owner entity
    owner_data = repo_data["owner"]
    owner_uri = graph.create_entity(
        "User",
        {
            "id": str(owner_data["id"]),
            "login": owner_data["login"],
            "url": owner_data["html_url"],
            "type": owner_data["type"]
        }
    )
    
    # Link repository to owner
    graph.create_relationship(
        repo_uri,
        "ownedBy",
        owner_uri
    )
    
    return repo_uri

def _transform_issues(self, graph: ABIGraph, issues: List[Dict], repository_uri: str) -> None:
    """Transform issue data into graph entities.
    
    Args:
        graph: The graph to add entities to
        issues: List of issue data from GitHub
        repository_uri: URI of the repository entity
    """
    for issue in issues:
        # Create issue entity
        issue_uri = graph.create_entity(
            "Issue",
            {
                "id": str(issue["id"]),
                "number": issue["number"],
                "title": issue["title"],
                "state": issue["state"],
                "created_at": issue["created_at"],
                "updated_at": issue["updated_at"],
                "url": issue["html_url"]
            }
        )
        
        # Link issue to repository
        graph.create_relationship(
            issue_uri,
            "belongsTo",
            repository_uri
        )
        
        # Create user entity for the creator
        user_data = issue["user"]
        user_uri = graph.create_entity(
            "User",
            {
                "id": str(user_data["id"]),
                "login": user_data["login"],
                "url": user_data["html_url"]
            }
        )
        
        # Link issue to creator
        graph.create_relationship(
            issue_uri,
            "createdBy",
            user_uri
        )
```

### 5. Add API Interface

Implement methods to expose the pipeline via API:

```python
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

def as_tools(self) -> list[StructuredTool]:
    """Returns a list of LangChain tools for this pipeline.
    
    Returns:
        list[StructuredTool]: List containing the pipeline tool
    """
    return [StructuredTool(
        name="extract_github_repository",
        description="Extracts data from a GitHub repository into the knowledge graph",
        func=lambda **kwargs: self.run(GithubRepositoryPipelineParameters(**kwargs)),
        args_schema=GithubRepositoryPipelineParameters
    )]

def as_api(self, router: APIRouter) -> None:
    """Adds API endpoints for this pipeline to the given router.
    
    Args:
        router (APIRouter): FastAPI router to add endpoints to
    """
    @router.post("/pipelines/github-repository")
    def run_github_pipeline(parameters: GithubRepositoryPipelineParameters):
        result = self.run(parameters)
        return {
            "success": True,
            "triples_count": len(result),
            "repository": parameters.repository
        }
```

### 6. Implement Utility Methods

Add helper methods for common operations:

```python
def _get_entity_by_external_id(self, graph: ABIGraph, entity_type: str, external_id: str) -> Optional[str]:
    """Find an entity in the graph by its external ID.
    
    Args:
        graph: The graph to search in
        entity_type: Type of entity to look for
        external_id: External ID to match
        
    Returns:
        Optional[str]: URI of the found entity, or None if not found
    """
    entities = graph.find_entities(
        entity_type,
        {"id": external_id}
    )
    
    return entities[0] if entities else None

def _create_or_get_label_entities(self, graph: ABIGraph, labels: List[Dict]) -> List[str]:
    """Create or retrieve label entities.
    
    Args:
        graph: The graph to add entities to
        labels: List of label data
        
    Returns:
        List[str]: List of label entity URIs
    """
    label_uris = []
    
    for label in labels:
        # Check if label already exists
        existing_uri = self._get_entity_by_external_id(
            graph, 
            "Label", 
            str(label["id"])
        )
        
        if existing_uri:
            label_uris.append(existing_uri)
        else:
            # Create new label entity
            label_uri = graph.create_entity(
                "Label",
                {
                    "id": str(label["id"]),
                    "name": label["name"],
                    "color": label.get("color", "")
                }
            )
            label_uris.append(label_uri)
    
    return label_uris
```

### 7. Testing Your Pipeline

Create tests for your pipeline:

```python
import unittest
from unittest.mock import MagicMock, patch

class TestGithubRepositoryPipeline(unittest.TestCase):
    """Tests for the GitHub Repository Pipeline."""
    
    def setUp(self):
        """Set up test environment."""
        self.github_integration = MagicMock()
        self.ontology_store = MagicMock()
        
        self.config = GithubRepositoryPipelineConfiguration(
            github_integration=self.github_integration,
            ontology_store=self.ontology_store,
            ontology_store_name="test_github_data"
        )
        
        self.pipeline = GithubRepositoryPipeline(self.config)
        
        # Mock responses
        self.mock_repo = {
            "id": 12345,
            "name": "test-repo",
            "full_name": "test-owner/test-repo",
            "description": "Test repository",
            "html_url": "https://github.com/test-owner/test-repo",
            "stargazers_count": 10,
            "forks_count": 5,
            "created_at": "2022-01-01T00:00:00Z",
            "updated_at": "2022-01-02T00:00:00Z",
            "owner": {
                "id": 67890,
                "login": "test-owner",
                "html_url": "https://github.com/test-owner",
                "type": "User"
            }
        }
        
        self.mock_issues = [
            {
                "id": 11111,
                "number": 1,
                "title": "Test issue",
                "state": "open",
                "created_at": "2022-01-01T00:00:00Z",
                "updated_at": "2022-01-02T00:00:00Z",
                "html_url": "https://github.com/test-owner/test-repo/issues/1",
                "user": {
                    "id": 67890,
                    "login": "test-owner",
                    "html_url": "https://github.com/test-owner"
                }
            }
        ]
        
    def test_pipeline_run(self):
        """Test running the pipeline."""
        # Setup mocks
        self.github_integration.get_repository.return_value = self.mock_repo
        self.github_integration.get_issues.return_value = self.mock_issues
        self.github_integration.get_pull_requests.return_value = []
        self.github_integration.get_contributors.return_value = []
        
        # Run pipeline
        params = GithubRepositoryPipelineParameters(
            repository="test-owner/test-repo"
        )
        result = self.pipeline.run(params)
        
        # Verify integration calls
        self.github_integration.get_repository.assert_called_once_with(
            "test-owner", "test-repo"
        )
        self.github_integration.get_issues.assert_called_once()
        self.github_integration.get_pull_requests.assert_called_once()
        self.github_integration.get_contributors.assert_called_once()
        
        # Verify ontology store call
        self.ontology_store.insert.assert_called_once_with(
            "test_github_data", 
            result
        )
```

### 8. Using the Pipeline in a Workflow

Example of using your pipeline in a workflow:

```python
from src.workflows import RepositoryAnalysisWorkflow
from src.workflows.repository_analysis import RepositoryAnalysisParameters

def analyze_repository(repo: str) -> Dict[str, Any]:
    """Analyze a GitHub repository.
    
    Args:
        repo: GitHub repository in format "owner/repo"
        
    Returns:
        Dict containing analysis results
    """
    # Set up the pipeline
    pipeline_config = GithubRepositoryPipelineConfiguration(
        github_integration=github_integration,
        ontology_store=ontology_store_service
    )
    pipeline = GithubRepositoryPipeline(pipeline_config)
    
    # Run the pipeline to extract data
    pipeline.run(
        GithubRepositoryPipelineParameters(
            repository=repo,
            include_issues=True,
            include_pull_requests=True,
            include_contributors=True
        )
    )
    
    # Set up and run the analysis workflow
    workflow = RepositoryAnalysisWorkflow(workflow_config)
    results = workflow.run(
        RepositoryAnalysisParameters(
            repository=repo
        )
    )
    
    return results
```

## Best Practices

### Separation of Concerns

- Keep extraction, transformation, and loading logic separate
- Create utility methods for reusable operations
- Use clear naming conventions for methods

### Performance Optimization

- Process data in batches when possible
- Implement incremental processing for large datasets
- Use efficient graph operations
- Consider caching for frequently accessed data

### Error Handling

- Implement proper error handling for API calls
- Handle partial failures gracefully
- Log detailed error information
- Consider recovery strategies for transient errors

### Graph Building

- Follow consistent entity and relationship naming conventions
- Reuse existing entities rather than creating duplicates
- Include relevant metadata (timestamps, source information)
- Ensure data quality and consistency

### Testing

- Test each component of the pipeline separately
- Create integration tests for the full pipeline
- Test with representative datasets
- Test edge cases and error conditions

## Advanced Pipeline Features

### Incremental Processing

For efficient updates of existing data:

```python
def run_incremental(
    self, 
    parameters: GithubRepositoryPipelineParameters, 
    since_timestamp: str
) -> Graph:
    """Run an incremental update of repository data.
    
    Args:
        parameters: Pipeline parameters
        since_timestamp: Only process data modified after this timestamp
        
    Returns:
        Graph containing new or updated data
    """
    graph = ABIGraph()
    owner, repo = parameters.repository.split('/')
    
    # Get only issues updated since the timestamp
    if parameters.include_issues:
        issues = self.__configuration.github_integration.get_issues(
            owner, 
            repo, 
            since=since_timestamp,
            max_results=parameters.max_items
        )
        self._transform_issues(graph, issues, repository_uri)
    
    # Similar for pull requests and other data
    # ...
    
    # Merge with existing data in the store
    self.__configuration.ontology_store.insert(
        self.__configuration.ontology_store_name,
        graph
    )
    
    return graph
```

### Data Validation

Implement validation for input and output data:

```python
def _validate_repository_data(self, repo_data: Dict) -> bool:
    """Validate repository data.
    
    Args:
        repo_data: Repository data to validate
        
    Returns:
        bool: True if valid, False otherwise
        
    Raises:
        ValueError: If required fields are missing
    """
    required_fields = ["id", "name", "full_name", "owner"]
    
    for field in required_fields:
        if field not in repo_data:
            raise ValueError(f"Required field '{field}' missing from repository data")
    
    # Validate owner data
    if not isinstance(repo_data["owner"], dict):
        raise ValueError("Owner data must be a dictionary")
        
    owner_required_fields = ["id", "login"]
    for field in owner_required_fields:
        if field not in repo_data["owner"]:
            raise ValueError(f"Required field '{field}' missing from owner data")
    
    return True
```

### Custom Graph Serialization

Add methods to customize graph serialization:

```python
def serialize_graph(self, graph: Graph, format: str = "turtle") -> str:
    """Serialize the graph to a string format.
    
    Args:
        graph: The graph to serialize
        format: Serialization format (turtle, json-ld, etc.)
        
    Returns:
        str: Serialized graph
    """
    valid_formats = ["turtle", "xml", "json-ld", "n3", "nt"]
    if format not in valid_formats:
        raise ValueError(f"Unsupported format: {format}. Must be one of {valid_formats}")
        
    return graph.serialize(format=format)
    
def export_to_file(self, graph: Graph, file_path: str, format: str = "turtle") -> None:
    """Export the graph to a file.
    
    Args:
        graph: The graph to export
        file_path: Path to the output file
        format: Serialization format
    """
    serialized = self.serialize_graph(graph, format)
    
    with open(file_path, 'w') as f:
        f.write(serialized)
```

## Next Steps

- Learn about [Writing Workflows](writing-workflows.md) to build higher-level processes using pipelines
- Explore [Managing Ontologies](managing-ontologies.md) to understand how pipeline data fits into the knowledge graph
- Check out [Building Integrations](building-integrations.md) to create more data sources for your pipelines 