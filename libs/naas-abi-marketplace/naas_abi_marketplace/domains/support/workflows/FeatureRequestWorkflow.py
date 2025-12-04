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
class FeatureRequestWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for GitHub support workflows.

    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
        data_store_path: Path to store cached data
        project_node_id: ID of the project to create the feature request in
        status_field_id: ID of the status field to create the feature request in
        priority_field_id: ID of the priority field to create the feature request in
        iteration_field_id: ID of the iteration field to create the feature request in
    """
    github_integration_config: GitHubIntegrationConfiguration
    github_graphql_integration_config: GitHubGraphqlIntegrationConfiguration
    data_store_path: str = field(default_factory=lambda: ABIModule.get_instance().configuration.datastore_path)
    project_node_id: str = field(default_factory=lambda: ABIModule.get_instance().configuration.project_node_id)
    status_field_id: str = field(default_factory=lambda: ABIModule.get_instance().configuration.status_field_id)
    priority_field_id: str = field(default_factory=lambda: ABIModule.get_instance().configuration.priority_field_id)
    iteration_field_id: str = field(default_factory=lambda: ABIModule.get_instance().configuration.iteration_field_id)


class FeatureRequestParameters(WorkflowParameters):
    """Parameters for feature request creation.

    Attributes:
        issue_title: Title of the feature request
        issue_body: Body content of the feature request
        repo_name: Name of the repository to create the feature request in
        assignees: Assignees of the feature request
        labels: Labels of the feature request
        priority_id: ID of the priority of the feature request
        status_id: ID of the status of the feature request
    """
    issue_title: Annotated[
        str, 
        Field(
            ...,
            description="The title of the feature request")
    ]
    issue_body: Annotated[
        str, 
        Field(
            ...,
            description="The description of the feature request")
    ]
    repo_name: Annotated[
        str,
        Field(
            ABIModule.get_instance().configuration.default_repository,
            description="The name of the repository to create the feature request in",
        ),
    ]
    labels: Annotated[
        list,
        Field(
            ["enhancement"],
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


class FeatureRequestWorkflow(Workflow):
    """Workflow class that handles feature request creation."""

    __configuration: FeatureRequestWorkflowConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: FeatureRequestWorkflowConfiguration):
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

    def create_feature_request(self, parameters: FeatureRequestParameters) -> Dict:
        """Creates a new feature request issue and adds it to the project."""
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
            assignees=parameters.assignees,
            labels=parameters.labels,
        )
        issue_repository_url = issue.get("repository_url", "")
        issue_path = issue_repository_url.split("https://api.github.com/repos/")[-1]
        self.__storage_utils.save_json(
            issue,
            os.path.join(self.__configuration.data_store_path, issue_path, "issues"),
            f"{issue.get('number')}.json",
        )

        # Add the issue to project using direct project_node_id
        issue_node_id = issue["node_id"]
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
                name="support_feature_request",
                description="Create a new feature request (GitHub) issue.",                
                func=lambda **kwargs: self.create_feature_request(FeatureRequestParameters(**kwargs)),
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
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None
