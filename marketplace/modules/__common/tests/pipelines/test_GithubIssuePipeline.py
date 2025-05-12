import pytest
from unittest.mock import Mock
from rdflib import Graph

from src.core.modules.common.pipelines.github.GithubIssuePipeline import (
    GithubIssuePipeline,
    GithubIssuePipelineConfiguration,
    GithubIssuePipelineParameters,
)
from src.core.modules.common.integrations.GithubIntegration import GithubIntegration
from src.core.modules.common.integrations.GithubGraphqlIntegration import (
    GithubGraphqlIntegration,
)
from abi.services.triple_store.TripleStoreService import TripleStoreService


@pytest.fixture
def mock_issue_data():
    return {
        "id": "123",
        "title": "Test Issue",
        "node_id": "I_123",
        "body": "Test Description",
        "html_url": "https://github.com/org/repo/issues/123",
        "state": "open",
        "labels": [{"name": "bug"}, {"name": "priority"}],
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-02T10:00:00Z",
        "closed_at": None,
        "repository_url": "https://api.github.com/repos/org/repo",
        "user": {
            "id": "user123",
            "login": "testuser",
            "html_url": "https://github.com/testuser",
        },
        "assignees": [
            {
                "id": "assignee123",
                "login": "assigneeuser",
                "html_url": "https://github.com/assigneeuser",
            }
        ],
    }


@pytest.fixture
def mock_project_data():
    return {"data": {"organization": {"projectV2": {"id": "project123"}}}}


@pytest.fixture
def mock_item_data():
    return {
        "data": {
            "node": {
                "projectItems": {
                    "nodes": [{"project": {"id": "project123"}, "id": "item123"}]
                }
            }
        }
    }


@pytest.fixture
def mock_item_details():
    return {
        "data": {
            "node": {
                "fieldValues": {
                    "nodes": [
                        {"field": {"name": "Status"}, "name": "In Progress"},
                        {"field": {"name": "Priority"}, "name": "High"},
                        {"field": {"name": "Estimate"}, "number": 5},
                    ]
                }
            }
        }
    }


def test_github_issue_pipeline(
    mock_issue_data, mock_project_data, mock_item_data, mock_item_details
):
    # Mock the integrations and services
    mock_github = Mock(spec=GithubIntegration)
    mock_github.get_issue.return_value = mock_issue_data

    mock_github_graphql = Mock(spec=GithubGraphqlIntegration)
    mock_github_graphql.get_project_node_id.return_value = mock_project_data
    mock_github_graphql.get_item_id_from_node_id.return_value = mock_item_data
    mock_github_graphql.get_item_details.return_value = mock_item_details

    mock_triple_store = Mock(spec=TripleStoreService)

    # Create pipeline configuration
    config = GithubIssuePipelineConfiguration(
        github_integration=mock_github,
        github_graphql_integration=mock_github_graphql,
        triple_store=mock_triple_store,
    )

    # Create pipeline parameters
    params = GithubIssuePipelineParameters(
        github_repository="org/repo", github_issue_id="123", github_project_id=1
    )

    # Create and run pipeline
    pipeline = GithubIssuePipeline(config)
    result = pipeline.run(params)

    # Assertions
    assert isinstance(result, Graph)
    mock_github.get_issue.assert_called_once_with("org/repo", "123")
    mock_triple_store.insert.assert_called_once()

    # Verify the graph contains expected data
    turtle_data = result.serialize(format="turtle")
    assert "Test Issue" in turtle_data
    assert "https://github.com/org/repo/issues/123" in turtle_data
    assert "testuser" in turtle_data
    assert "assigneeuser" in turtle_data


def test_github_issue_pipeline_without_project():
    # Mock the integrations and services
    mock_github = Mock(spec=GithubIntegration)
    mock_github.get_issue.return_value = {
        "id": "123",
        "title": "Simple Issue",
        "node_id": "I_123",
        "body": "Description",
        "html_url": "https://github.com/org/repo/issues/123",
        "state": "open",
        "labels": [],
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-02T10:00:00Z",
        "closed_at": None,
        "repository_url": "https://api.github.com/repos/org/repo",
        "user": {
            "id": "user123",
            "login": "testuser",
            "html_url": "https://github.com/testuser",
        },
        "assignees": [],
    }

    mock_github_graphql = Mock(spec=GithubGraphqlIntegration)
    mock_triple_store = Mock(spec=TripleStoreService)

    # Create pipeline configuration
    config = GithubIssuePipelineConfiguration(
        github_integration=mock_github,
        github_graphql_integration=mock_github_graphql,
        triple_store=mock_triple_store,
    )

    # Create pipeline parameters
    params = GithubIssuePipelineParameters(
        github_repository="org/repo",
        github_issue_id="123",
        github_project_id=0,  # No project
    )

    # Create and run pipeline
    pipeline = GithubIssuePipeline(config)
    result = pipeline.run(params)

    # Assertions
    assert isinstance(result, Graph)
    mock_github.get_issue.assert_called_once_with("org/repo", "123")
    mock_github_graphql.get_project_node_id.assert_not_called()
    mock_triple_store.insert.assert_called_once()
