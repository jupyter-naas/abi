from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.marketplace.modules.applications.github.integrations.GitHubIntegration import GitHubIntegration, GitHubIntegrationConfiguration
from src.marketplace.modules.applications.github.integrations.GitHubGraphqlIntegration import GitHubGraphqlIntegration, GitHubGraphqlIntegrationConfiguration
from src import config
from dataclasses import dataclass
from pydantic import Field
from typing import List, Dict
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from enum import Enum

@dataclass
class FeatureRequestWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for GitHub support workflows.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
    """
    github_integration_config: GitHubIntegrationConfiguration
    github_graphql_integration_config: GitHubGraphqlIntegrationConfiguration
    repo_name: str = config.github_support_repository
    project_node_id: str = "PVT_kwDOBESWNM4AKRt3"

class FeatureRequestParameters(WorkflowParameters):
    """Parameters for feature request creation.
    
    Attributes:
        issue_title: Title of the feature request
        issue_body: Body content of the feature request
    """
    issue_title: str = Field(..., description="The title of the feature request")
    issue_body: str = Field(..., description="The description of the feature request")

class FeatureRequestWorkflow(Workflow):
    """Workflow class that handles feature request creation."""
    __configuration: FeatureRequestWorkflowConfiguration
    
    def __init__(self, configuration: FeatureRequestWorkflowConfiguration):
        self.__configuration = configuration
        self.__github_integration = GitHubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GitHubGraphqlIntegration(self.__configuration.github_graphql_integration_config)

    def create_feature_request(self, parameters: FeatureRequestParameters) -> Dict:
        """Creates a new feature request issue and adds it to the project."""
        assignees: list = []
        labels = ["enhancement"]
        status_field_id = "PVTSSF_lADOBESWNM4AKRt3zgGZRV8"
        status_option_id = "97363483"

        # Create an issue
        issue = self.__github_integration.create_issue(
            repo_name=self.__configuration.repo_name,
            title=parameters.issue_title,
            body=parameters.issue_body,
            assignees=assignees,
            labels=labels
        )
        
        # Add the issue to project using direct project_node_id
        issue_node_id = issue['node_id']
        logger.debug(f"Issue node ID: {issue_node_id}")
        self.__github_graphql_integration.add_issue_to_project(
            project_node_id=self.__configuration.project_node_id,
            issue_node_id=issue_node_id,
            status_field_id=status_field_id,
            status_option_id=status_option_id,
        )
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
                func=lambda issue_title, issue_body: self.create_feature_request(FeatureRequestParameters(issue_title=issue_title, issue_body=issue_body)),
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
