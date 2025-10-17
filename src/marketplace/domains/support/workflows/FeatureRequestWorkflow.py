from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.marketplace.applications.github.integrations.GitHubIntegration import GitHubIntegration, GitHubIntegrationConfiguration
from src.marketplace.applications.github.integrations.GitHubGraphqlIntegration import GitHubGraphqlIntegration, GitHubGraphqlIntegrationConfiguration
from src import config
from dataclasses import dataclass
from pydantic import Field
from typing import List, Dict, Annotated, Optional
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from enum import Enum
import os
from src.utils.Storage import save_json


@dataclass
class FeatureRequestWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for GitHub support workflows.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
    """
    github_integration_config: GitHubIntegrationConfiguration
    github_graphql_integration_config: GitHubGraphqlIntegrationConfiguration
    data_store_path: str = "datastore/support"
    project_node_id: str = "PVT_kwDOBESWNM4AKRt3"
    status_field_id: str = "PVTSSF_lADOBESWNM4AKRt3zgGZRV8"
    priority_field_id: str = "PVTSSF_lADOBESWNM4AKRt3zgGac0g"
    iteration_field_id: str = "PVTIF_lADOBESWNM4AKRt3zgGZRc4"


class FeatureRequestParameters(WorkflowParameters):
    """Parameters for feature request creation.
    
    Attributes:
        issue_title: Title of the feature request
        issue_body: Body content of the feature request
    """
    issue_title: Annotated[str, Field(..., description="The title of the feature request")]
    issue_body: Annotated[str, Field(..., description="The description of the feature request")]
    repo_name: Optional[Annotated[str, Field(..., description="The name of the repository to create the feature request in")]] = config.github_repository
    assignees: Optional[Annotated[list, Field(..., description="The assignees of the feature request")]] = []
    labels: Optional[Annotated[list, Field(..., description="The labels of the feature request")]] = ["enhancement"]
    priority_id: Optional[Annotated[str, Field(..., description="The ID of the priority of the feature request")]] = "4fb76f2d"
    status_id: Optional[Annotated[str, Field(..., description="The ID of the status of the feature request")]] = "97363483"


class FeatureRequestWorkflow(Workflow):
    """Workflow class that handles feature request creation."""
    __configuration: FeatureRequestWorkflowConfiguration
    
    def __init__(self, configuration: FeatureRequestWorkflowConfiguration):
        self.__configuration = configuration
        self.__github_integration = GitHubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GitHubGraphqlIntegration(self.__configuration.github_graphql_integration_config)

    def create_feature_request(self, parameters: FeatureRequestParameters) -> Dict:
        """Creates a new feature request issue and adds it to the project."""
        # Get the current iteration ID
        iteration_option_id = self.__github_graphql_integration.get_current_iteration_id(self.__configuration.project_node_id)

        # Create an issue
        issue = self.__github_integration.create_issue(
            repo_name=parameters.repo_name,
            title=parameters.issue_title,
            body=parameters.issue_body,
            assignees=parameters.assignees,
            labels=parameters.labels
        )
        issue_repository_url = issue.get("repository_url")
        issue_path = issue_repository_url.split("https://api.github.com/repos/")[-1]
        save_json(issue, os.path.join(self.__configuration.data_store_path, issue_path, "issues"), f"{issue.get('number')}.json")

        # Add the issue to project using direct project_node_id
        issue_node_id = issue['node_id']
        logger.debug(f"Issue node ID: {issue_node_id}")
        issue_graphql = self.__github_graphql_integration.add_issue_to_project(
            project_node_id=self.__configuration.project_node_id,
            status_field_id=self.__configuration.status_field_id,
            priority_field_id=self.__configuration.priority_field_id,
            iteration_field_id=self.__configuration.iteration_field_id,
            issue_node_id=issue_node_id,
            status_option_id=parameters.status_id,
            priority_option_id=parameters.priority_id,
            iteration_option_id=iteration_option_id
        )
        save_json(issue_graphql, os.path.join(self.__configuration.data_store_path, issue_path, "issues"), f"{issue.get('number')}_graphql.json")
        return issue
    
    def as_tools(self) -> List[BaseTool]:
        """Returns a list of LangChain tools for all support workflows.
        
        Returns:
            List[StructuredTool]: List containing all support workflow tools
        """
        return [
            StructuredTool(
                name="feature_request",
                description="Ask for a new feature request to support team.",
                func=lambda **kwargs: self.create_feature_request(FeatureRequestParameters(**kwargs)),
                args_schema=FeatureRequestParameters
            ),
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None
