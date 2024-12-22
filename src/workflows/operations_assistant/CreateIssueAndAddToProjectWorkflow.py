from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from src import config
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from typing import Optional, List
from abi import logger
import pydash as _
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class CreateIssueAndAddToProjectWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for creating GitHub issues and adding them to projects.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
    """
    github_integration_config: GithubIntegrationConfiguration
    github_graphql_integration_config: GithubGraphqlIntegrationConfiguration

class CreateIssueAndAddToProjectParameters(WorkflowParameters):
    """Parameters for creating GitHub issues and adding them to projects.
    
    Attributes:
        repo_name: Repository name in format owner/repo
        issue_title: Title of the issue
        issue_body: Body content of the issue
        project_id: Project number (from GitHub project URL). Optional if configured in config.github_project_id
        assignees: List of assignees
        labels: List of labels
        status_field_id: Field ID for status column
        priority_field_id: Field ID for priority column
        status_option_id: Option ID for status value
        priority_option_id: Option ID for priority value
    """
    repo_name: str = Field(..., description="Repository name in format owner/repo")
    issue_title: str = Field(..., description="Title of the issue")
    issue_body: str = Field(..., description="Body content of the issue")
    project_id: Optional[int] = Field(0, description="Project number from GitHub project URL (optional if configured globally)")
    assignees: Optional[List[str]] = Field(default_factory=list, description="List of GitHub usernames to assign")
    labels: Optional[List[str]] = Field(default_factory=list, description="List of labels to add")
    status_field_id: Optional[str] = Field(None, description="Field ID for status column")
    priority_field_id: Optional[str] = Field(None, description="Field ID for priority column")
    status_option_id: Optional[str] = Field(None, description="Option ID for status value")
    priority_option_id: Optional[str] = Field(None, description="Option ID for priority value")

class CreateIssueAndAddToProjectWorkflow(Workflow):
    __configuration: CreateIssueAndAddToProjectWorkflowConfiguration
    
    def __init__(self, configuration: CreateIssueAndAddToProjectWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__github_integration = GithubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GithubGraphqlIntegration(self.__configuration.github_graphql_integration_config)

    def run(self, parameters: CreateIssueAndAddToProjectParameters) -> str:
        # Create an issue
        issue = self.__github_integration.create_issue(
            repo_name=parameters.repo_name,
            title=parameters.issue_title,
            body=parameters.issue_body,
            assignees=parameters.assignees,
            labels=parameters.labels
        )
        # Get project node id
        if parameters.project_id != 0 or config.github_project_id:
            organization = parameters.repo_name.split("/")[0]
            project_id = parameters.project_id if parameters.project_id != 0 else config.github_project_id
            project_data : dict = self.__github_graphql_integration.get_project_node_id(organization, project_id)
            project_node_id = _.get(project_data, "data.organization.projectV2.id")
            logger.debug(f"Project node ID: {project_node_id}")

            # Add the issue to a project
            issue_node_id = issue['node_id']
            logger.debug(f"Issue node ID: {issue_node_id}")
            self.__github_graphql_integration.add_issue_to_project(
                project_node_id=project_node_id,
                issue_node_id=issue_node_id,
                status_field_id=parameters.status_field_id,
                priority_field_id=parameters.priority_field_id,
                status_option_id=parameters.status_option_id,
                priority_option_id=parameters.priority_option_id
            )
        else:
            logger.debug("No project ID provided, skipping project data")
        
        return f"Issue '{parameters.issue_title}' created and added to project: {issue}."
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow."""
        return [StructuredTool(
            name="create_github_issue",
            description="Creates a GitHub issue and optionally adds it to a project with status and priority settings",
            func=lambda **kwargs: self.run(CreateIssueAndAddToProjectParameters(**kwargs)),
            args_schema=CreateIssueAndAddToProjectParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router."""
        @router.post("/create_issue_and_add_to_project")
        def create_issue_and_add_to_project(parameters: CreateIssueAndAddToProjectParameters):
            return self.run(parameters)