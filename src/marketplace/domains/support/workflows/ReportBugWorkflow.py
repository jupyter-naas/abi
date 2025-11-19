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
class ReportBugWorkflowConfiguration(WorkflowConfiguration):
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


class ReportBugParameters(WorkflowParameters):
    """Parameters for bug report creation.
    
    Attributes:
        issue_title: Title of the bug report
        issue_body: Body content of the bug report
    """
    issue_title: Annotated[str, Field(..., description="The title of the bug report")]
    issue_body: Annotated[str, Field(..., description="The description of the bug, including steps to reproduce")]
    repo_name: Annotated[str, Field(config.github_repository, description="The name of the repository to create the bug report in")]
    assignees: Annotated[Optional[list], Field([], description="The assignees of the bug report")]
    labels: Annotated[Optional[list], Field(["bug"], description="The labels of the bug report")]
    priority_id: Annotated[Optional[str], Field("4fb76f2d", description="The ID of the priority of the bug report")]
    status_id: Annotated[Optional[str], Field("97363483", description="The ID of the status of the bug report")]
    

class ReportBugWorkflow(Workflow):
    """Workflow class that handles bug report creation."""
    __configuration: ReportBugWorkflowConfiguration
    
    def __init__(self, configuration: ReportBugWorkflowConfiguration):
        self.__configuration = configuration
        self.__github_integration = GitHubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GitHubGraphqlIntegration(self.__configuration.github_graphql_integration_config)

    def report_bug(self, parameters: ReportBugParameters) -> Dict:
        """Creates a new bug report issue and adds it to the project."""
        # Get the current iteration ID
        iteration_option_id = self.__github_graphql_integration.get_current_iteration_id(self.__configuration.project_node_id)

        # Create an issue
        issue = self.__github_integration.create_issue(
            repo_name=parameters.repo_name,
            title=parameters.issue_title,
            body=parameters.issue_body,
            labels=parameters.labels,
            assignees=parameters.assignees
        )
        issue_repository_url = issue.get("repository_url", "")
        issue_path = issue_repository_url.split("https://api.github.com/repos/")[-1]
        save_json(issue, os.path.join(self.__configuration.data_store_path, issue_path, "issues"), f"{issue.get('number')}.json")
        
        # Add the issue to project using direct project_node_id
        issue_node_id = issue.get('node_id', "")
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
                name="report_bug",
                description="Report a bug to the support team.",
                func=lambda **kwargs: self.report_bug(ReportBugParameters(**kwargs)),
                args_schema=ReportBugParameters
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
