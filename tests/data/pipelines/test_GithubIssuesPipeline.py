# import pytest
# from unittest.mock import Mock, patch
# from src.data.pipelines.github.GithubIssuesPipeline import (
#     GithubIssuesPipeline,
#     GithubIssuesPipelineConfiguration,
#     GithubIssuesPipelineParameters,
# )
# from src.integrations.GithubIntegration import GithubIntegration
# from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration
# from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
# from abi.utils.Graph import ABIGraph

# @pytest.fixture
# def mock_github_integration():
#     integration = Mock(spec=GithubIntegration)
#     integration.get_issues.return_value = [
#         {"number": 1, "title": "Test Issue 1"},
#         {"number": 2, "title": "Test Issue 2"},
#     ]
#     return integration

# @pytest.fixture
# def mock_github_graphql_integration():
#     integration = Mock(spec=GithubGraphqlIntegration)
#     integration.get_project_node_id.return_value = {
#         "data": {
#             "organization": {
#                 "projectV2": {
#                     "id": "test_project_node_id"
#                 }
#             }
#         }
#     }
#     return integration

# @pytest.fixture
# def mock_ontology_store():
#     store = Mock(spec=IOntologyStoreService)
#     return store

# @pytest.fixture
# def pipeline(mock_github_integration, mock_github_graphql_integration, mock_ontology_store):
#     config = GithubIssuesPipelineConfiguration(
#         github_integration=mock_github_integration,
#         github_graphql_integration=mock_github_graphql_integration,
#         ontology_store=mock_ontology_store,
#         ontology_store_name="test_github"
#     )
#     return GithubIssuesPipeline(config)

# def test_pipeline_initialization(pipeline):
#     assert isinstance(pipeline, GithubIssuesPipeline)

# def test_pipeline_run_without_project_id(pipeline, mock_github_integration):
#     params = GithubIssuesPipelineParameters(
#         github_repositories=["owner/repo"],
#         limit=2,
#         state="all",
#         github_project_id=0
#     )
    
#     result = pipeline.run(params)
    
#     assert isinstance(result, ABIGraph)
#     mock_github_integration.get_issues.assert_called_once_with(
#         "owner/repo",
#         state="all",
#         limit=2
#     )

# def test_pipeline_run_with_project_id(pipeline, mock_github_integration, mock_github_graphql_integration):
#     params = GithubIssuesPipelineParameters(
#         github_repositories=["owner/repo"],
#         limit=2,
#         state="all",
#         github_project_id=123
#     )
    
#     result = pipeline.run(params)
    
#     assert isinstance(result, ABIGraph)
#     mock_github_integration.get_issues.assert_called_once()
#     mock_github_graphql_integration.get_project_node_id.assert_called_once_with(
#         "owner",
#         123
#     )

# def test_pipeline_run_multiple_repositories(pipeline, mock_github_integration):
#     params = GithubIssuesPipelineParameters(
#         github_repositories=["owner1/repo1", "owner2/repo2"],
#         limit=2,
#         state="all"
#     )
    
#     result = pipeline.run(params)
    
#     assert isinstance(result, ABIGraph)
#     assert mock_github_integration.get_issues.call_count == 2
#     mock_github_integration.get_issues.assert_any_call(
#         "owner1/repo1",
#         state="all",
#         limit=2
#     )
#     mock_github_integration.get_issues.assert_any_call(
#         "owner2/repo2",
#         state="all",
#         limit=2
#     ) 