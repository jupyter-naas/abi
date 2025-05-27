from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.core.modules.support.integrations.GithubIntegration import (
    GithubIntegration,
    GithubIntegrationConfiguration,
)
from src.core.modules.support.integrations.GithubGraphqlIntegration import (
    GithubGraphqlIntegration,
    GithubGraphqlIntegrationConfiguration,
)
from src import config
from dataclasses import dataclass
from pydantic import Field
from typing import List, Dict, Optional, Union
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from langchain_core.tools import BaseTool
from enum import Enum


@dataclass
class GitHubSupportWorkflowsConfiguration(WorkflowConfiguration):
    """Configuration for GitHub support workflows.

    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
    """

    github_integration_config: GithubIntegrationConfiguration
    github_graphql_integration_config: GithubGraphqlIntegrationConfiguration


class ListIssuesParameters(WorkflowParameters):
    """Parameters for listing issues.

    Attributes:
        repo_name: Repository name in format owner/repo
        state: Filter issues by state
        limit: Maximum number of issues to return
    """

    repo_name: str = Field(
        config.github_support_repository,
        description=f"Repository name in format owner/repo. Ask the users if they want to use the default {config.github_support_repository} or a different repository.",
    )


class GetIssueParameters(WorkflowParameters):
    """Parameters for getting an issue.

    Attributes:
        repo_name: Repository name in format owner/repo
        issue_number: Issue number
    """

    repo_name: str = Field(
        config.github_support_repository,
        description=f"Repository name in format owner/repo. Ask the users if they want to use the default {config.github_support_repository} or a different repository.",
    )
    issue_number: int = Field(..., description="The number of the issue to get")


class ReportBugParameters(WorkflowParameters):
    """Parameters for bug report creation.

    Attributes:
        repo_name: Repository name in format owner/repo
        issue_title: Title of the bug report
        issue_body: Body content of the bug report
    """

    repo_name: str = Field(
        config.github_support_repository,
        description=f"Repository name in format owner/repo. Ask the users if they want to use the default {config.github_support_repository} or a different repository.",
    )
    issue_title: str = Field(..., description="The title of the bug report")
    issue_body: str = Field(
        ..., description="The description of the bug, including steps to reproduce"
    )


class FeatureRequestParameters(WorkflowParameters):
    """Parameters for feature request creation.

    Attributes:
        repo_name: Repository name in format owner/repo
        issue_title: Title of the feature request
        issue_body: Body content of the feature request
    """

    repo_name: str = Field(
        config.github_support_repository,
        description=f"Repository name in format owner/repo. Ask the users if they want to use the default {config.github_support_repository} or a different repository.",
    )
    issue_title: str = Field(..., description="The title of the feature request")
    issue_body: str = Field(..., description="The description of the feature request")


class GitHubSupportWorkflows(Workflow):
    """Workflow class that handles GitHub support-related operations:
    - Listing existing issues in repository
    - Getting an issue details
    - Creating bug reports
    - Creating feature requests

    Attributes:
        configuration: Configuration for GitHub support workflows
    """

    __configuration: GitHubSupportWorkflowsConfiguration

    def __init__(self, configuration: GitHubSupportWorkflowsConfiguration):
        self.__configuration = configuration
        self.__github_integration = GithubIntegration(
            self.__configuration.github_integration_config
        )
        self.__github_graphql_integration = GithubGraphqlIntegration(
            self.__configuration.github_graphql_integration_config
        )

    def list_issues(self, parameters: ListIssuesParameters) -> List:
        """Lists GitHub issues from a repository."""
        issues = self.__github_integration.list_issues(
            repo_name=parameters.repo_name, state="open", limit=-1
        )
        logger.info(f"Found {len(issues)} issues:")
        return [
            {"number": issue["number"], "title": issue["title"]} for issue in issues
        ]

    def get_issue(self, parameters: GetIssueParameters) -> Dict:
        """Gets details of a GitHub issue."""
        issue = self.__github_integration.get_issue(
            repo_name=parameters.repo_name, 
            issue_id=parameters.issue_number
        )
        return issue

    def report_bug(self, parameters: ReportBugParameters) -> Dict:
        """Creates a new bug report issue and adds it to the project."""
        project_node_id = "PVT_kwDOBESWNM4AKRt3"
        assignees: List[str] = []
        labels = ["bug"]
        status_field_id = "PVTSSF_lADOBESWNM4AKRt3zgGZRV8"
        priority_field_id = "PVTSSF_lADOBESWNM4AKRt3zgGac0g"
        status_option_id = "97363483"
        priority_option_id = "4fb76f2d"

        # Create an issue
        issue = self.__github_integration.create_issue(
            repo_name=parameters.repo_name,
            title=parameters.issue_title,
            body=parameters.issue_body,
            labels=labels,
            assignees=assignees,
        )

        # Add the issue to project using direct project_node_id
        issue_node_id = issue["node_id"]
        logger.debug(f"Issue node ID: {issue_node_id}")
        self.__github_graphql_integration.add_issue_to_project(
            project_node_id=project_node_id,
            issue_node_id=issue_node_id,
            status_field_id=status_field_id,
            priority_field_id=priority_field_id,
            status_option_id=status_option_id,
            priority_option_id=priority_option_id,
        )
        return issue

    def create_feature_request(self, parameters: FeatureRequestParameters) -> Dict:
        """Creates a new feature request issue and adds it to the project."""
        repo_name = parameters.repo_name
        project_node_id = "PVT_kwDOBESWNM4AKRt3"
        assignees: List[str] = []
        labels = ["enhancement"]
        status_field_id = "PVTSSF_lADOBESWNM4AKRt3zgGZRV8"
        status_option_id = "97363483"

        # Create an issue
        issue = self.__github_integration.create_issue(
            repo_name=repo_name,
            title=parameters.issue_title,
            body=parameters.issue_body,
            assignees=assignees,
            labels=labels,
        )

        # Add the issue to project using direct project_node_id
        issue_node_id = issue["node_id"]
        logger.debug(f"Issue node ID: {issue_node_id}")
        self.__github_graphql_integration.add_issue_to_project(
            project_node_id=project_node_id,
            issue_node_id=issue_node_id,
            status_field_id=status_field_id,
            status_option_id=status_option_id,
        )
        return issue

    def as_tools(self) -> List["BaseTool"]:
        """Returns a list of LangChain tools for all support workflows.

        Returns:
            List[StructuredTool]: List containing all support workflow tools
        """
        return [
            StructuredTool(
                name="support_agent_list_issues",
                description="Lists feature requests and bug reports from GitHub support repository.",
                func=lambda repo_name: self.list_issues(
                    ListIssuesParameters(repo_name=repo_name)
                ),
                args_schema=ListIssuesParameters,
            ),
            StructuredTool(
                name="support_agent_get_details",
                description="Get details from feature requests and bug reports (issue number) from GitHub support repository.",
                func=lambda repo_name, issue_number: self.get_issue(
                    GetIssueParameters(repo_name=repo_name, issue_number=issue_number)
                ),
                args_schema=GetIssueParameters,
            ),
            StructuredTool(
                name="support_agent_create_bug_report",
                description="Create or post a bug report.",
                func=lambda repo_name, issue_title, issue_body: self.report_bug(
                    ReportBugParameters(
                        repo_name=repo_name,
                        issue_title=issue_title,
                        issue_body=issue_body,
                    )
                ),
                args_schema=ReportBugParameters,
            ),
            StructuredTool(
                name="support_agent_create_feature_request",
                description="Create or post a feature request.",
                func=lambda repo_name,
                issue_title,
                issue_body: self.create_feature_request(
                    FeatureRequestParameters(
                        repo_name=repo_name,
                        issue_title=issue_title,
                        issue_body=issue_body,
                    )
                ),
                args_schema=FeatureRequestParameters,
            ),
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: Optional[List[Union[str, Enum]]] = None
    ) -> None:
        """Adds API endpoints for all support workflows to the given router.

        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """

        @router.post("/report_bug")
        def report_bug(parameters: ReportBugParameters):
            return self.report_bug(parameters)

        @router.post("/list_issues")
        def list_issues(parameters: ListIssuesParameters):
            return self.list_issues(parameters)
