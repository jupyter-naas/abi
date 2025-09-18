from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.marketplace.applications.github.integrations.GitHubIntegration import GitHubIntegration, GitHubIntegrationConfiguration
from src.marketplace.applications.github.integrations.GitHubGraphqlIntegration import GitHubGraphqlIntegration, GitHubGraphqlIntegrationConfiguration
from src import config
from dataclasses import dataclass
from pydantic import Field
from typing import List, Dict
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from enum import Enum

@dataclass
class ReportBugWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for GitHub support workflows.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
    """
    github_integration_config: GitHubIntegrationConfiguration
    github_graphql_integration_config: GitHubGraphqlIntegrationConfiguration
    repo_name: str = config.github_support_repository
    project_node_id: str = "PVT_kwDOBESWNM4AKRt3"

class ReportBugParameters(WorkflowParameters):
    """Parameters for bug report creation.
    
    Attributes:
        issue_title: Title of the bug report
        issue_body: Body content of the bug report
    """
    issue_title: str = Field(..., description="The title of the bug report")
    issue_body: str = Field(..., description="The description of the bug, including steps to reproduce")

class ReportBugWorkflow(Workflow):
    """Workflow class that handles bug report creation."""
    __configuration: ReportBugWorkflowConfiguration
    
    def __init__(self, configuration: ReportBugWorkflowConfiguration):
        self.__configuration = configuration
        self.__github_integration = GitHubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GitHubGraphqlIntegration(self.__configuration.github_graphql_integration_config)

    def report_bug(self, parameters: ReportBugParameters) -> Dict:
        """Creates a new bug report issue and adds it to the project."""
        assignees: list = []
        labels = ["bug"]
        status_field_id = "PVTSSF_lADOBESWNM4AKRt3zgGZRV8"
        priority_field_id = "PVTSSF_lADOBESWNM4AKRt3zgGac0g"
        status_option_id = "97363483"
        priority_option_id = "4fb76f2d"

        # Create an issue
        issue = self.__github_integration.create_issue(
            repo_name=self.__configuration.repo_name,
            title=parameters.issue_title,
            body=parameters.issue_body,
            labels=labels,
            assignees=assignees
        )
        
        # Add the issue to project using direct project_node_id
        issue_node_id = issue['node_id']
        logger.debug(f"Issue node ID: {issue_node_id}")
        self.__github_graphql_integration.add_issue_to_project(
            project_node_id=self.__configuration.project_node_id,
            issue_node_id=issue_node_id,
            status_field_id=status_field_id,
            priority_field_id=priority_field_id,
            status_option_id=status_option_id,
            priority_option_id=priority_option_id
        )
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
                func=lambda issue_title, issue_body: self.report_bug(ReportBugParameters(issue_title=issue_title, issue_body=issue_body)),
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
