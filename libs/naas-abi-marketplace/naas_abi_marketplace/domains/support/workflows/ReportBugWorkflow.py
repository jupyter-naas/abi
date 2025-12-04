import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Dict, List, Optional
from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_core import logger
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
    GitHubGraphqlIntegration,
    GitHubGraphqlIntegrationConfiguration,
)
from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
    GitHubIntegration,
    GitHubIntegrationConfiguration,
)
from pydantic import Field
from naas_abi_marketplace.domains.support import ABIModule


@dataclass
class ReportBugWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for GitHub support workflows.

    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
        data_store_path: Path to store cached data
        project_node_id: ID of the project to create the bug report in
        status_field_id: ID of the status field to create the bug report in
        priority_field_id: ID of the priority field to create the bug report in
        iteration_field_id: ID of the iteration field to create the bug report in
    """
    github_integration_config: GitHubIntegrationConfiguration
    github_graphql_integration_config: GitHubGraphqlIntegrationConfiguration
    data_store_path: str = field(default_factory=lambda: ABIModule.get_instance().configuration.datastore_path)
    project_node_id: str = field(default_factory=lambda: ABIModule.get_instance().configuration.project_node_id)
    status_field_id: str = field(default_factory=lambda: ABIModule.get_instance().configuration.status_field_id)
    priority_field_id: str = field(default_factory=lambda: ABIModule.get_instance().configuration.priority_field_id)
    iteration_field_id: str = field(default_factory=lambda: ABIModule.get_instance().configuration.iteration_field_id)


class ReportBugParameters(WorkflowParameters):
    """Parameters for bug report creation.

    Attributes:
        issue_title: Title of the bug report
        issue_body: Body content of the bug report
        repo_name: Name of the repository to create the bug report in
        assignees: Assignees of the bug report
        labels: Labels of the bug report
        priority_id: ID of the priority of the bug report
        status_id: ID of the status of the bug report
    """
    issue_title: Annotated[
        str, 
        Field(
            ..., 
            description="The title of the bug report"
        )
    ]
    issue_body: Annotated[
        str,
        Field(
            ..., 
            description="The description of the bug, including steps to reproduce"
        ),
    ]
    repo_name: Annotated[
        str,
        Field(
            ABIModule.get_instance().configuration.default_repository,
            description="The name of the repository to create the bug report in",
        ),
    ]
    labels: Annotated[
        list,
        Field(
            ["bug"],
            description="The labels of the bug report"
        )
    ]
    priority_id: Annotated[
            str, 
            Field(
                ABIModule.get_instance().configuration.priority_option_id,
                description="The ID of the priority of the bug report"
            )
    ]
    status_id: Annotated[
        str, 
        Field(
            ABIModule.get_instance().configuration.status_option_id,
            description="The ID of the status of the bug report"
        )
    ]
    assignees: Optional[
        Annotated[
            list,
            Field(description="The assignees of the bug report")
        ]
    ] = []


class ReportBugWorkflow(Workflow):
    """Workflow class that handles bug report creation."""

    __configuration: ReportBugWorkflowConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: ReportBugWorkflowConfiguration):
        self.__configuration = configuration
        self.__github_integration = GitHubIntegration(
            self.__configuration.github_integration_config
        )
        self.__github_graphql_integration = GitHubGraphqlIntegration(
            self.__configuration.github_graphql_integration_config
        )
        self.__storage_utils = StorageUtils(
            ABIModule.get_instance().engine.services.object_storage
        )

    def report_bug(self, parameters: ReportBugParameters) -> Dict:
        """Creates a new bug report issue and adds it to the project."""
        # Get the current iteration ID
        iteration_option_id = (
            self.__github_graphql_integration.get_current_iteration_id(
                self.__configuration.project_node_id
            )
        )

        # Create an issue
        issue = self.__github_integration.create_issue(
            repo_name=parameters.repo_name,
            title=parameters.issue_title,
            body=parameters.issue_body,
            labels=parameters.labels,
            assignees=parameters.assignees,
        )
        issue_repository_url = issue.get("repository_url", "")
        issue_path = issue_repository_url.split("https://api.github.com/repos/")[-1]
        self.__storage_utils.save_json(
            issue,
            os.path.join(self.__configuration.data_store_path, issue_path, "issues"),
            f"{issue.get('number')}.json",
        )

        # Add the issue to project using direct project_node_id
        issue_node_id = issue.get("node_id", "")
        logger.debug(f"Issue node ID: {issue_node_id}")
        issue_graphql = self.__github_graphql_integration.add_issue_to_project(
            project_node_id=self.__configuration.project_node_id,
            status_field_id=self.__configuration.status_field_id,
            priority_field_id=self.__configuration.priority_field_id,
            iteration_field_id=self.__configuration.iteration_field_id,
            issue_node_id=issue_node_id,
            status_option_id=parameters.status_id,
            priority_option_id=parameters.priority_id,
            iteration_option_id=iteration_option_id,
        )
        self.__storage_utils.save_json(
            issue_graphql,
            os.path.join(self.__configuration.data_store_path, issue_path, "issues"),
            f"{issue.get('number')}_graphql.json",
        )
        return issue

    def as_tools(self) -> List[BaseTool]:
        """Returns a list of LangChain tools for all support workflows.

        Returns:
            List[StructuredTool]: List containing all support workflow tools
        """
        return [
            StructuredTool(
                name="support_bug_report",
                description="Create a new bug report (GitHub) issue.",
                func=lambda **kwargs: self.report_bug(ReportBugParameters(**kwargs)),
                args_schema=ReportBugParameters,
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
