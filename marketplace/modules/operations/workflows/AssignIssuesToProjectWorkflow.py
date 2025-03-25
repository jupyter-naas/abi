from abi.workflow import Workflow, WorkflowConfiguration
from src.core.modules.common.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.core.modules.common.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional
from abi import logger
import pydash as _
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

LOGO_URL = "https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"

@dataclass
class AssignIssuesToProjectWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for assigning GitHub issues to a project.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
    """
    github_integration_config: GithubIntegrationConfiguration
    github_graphql_integration_config: GithubGraphqlIntegrationConfiguration

class AssignIssuesToProjectWorkflowParameters(WorkflowParameters):
    """Parameters for AssignIssuesToProjectWorkflow execution.
    
    Attributes:
        repo_name: Repository name in format owner/repo
        project_id: Project number (from GitHub project URL)
        state: Issue state to filter by (default: "open")
        status_field_id: Field ID for status column
        priority_field_id: Field ID for priority column
        status_option_id: Option ID for status value
        priority_option_id: Option ID for priority value
    """
    repo_name: str = Field(..., description="The repository name in format owner/repo")
    project_id: int = Field(..., description="The project number in GitHub (from Project URL)")
    state: str = Field("open", description="Issue state to filter by")
    status_field_id: Optional[str] = Field(None, description="The field ID for the status column in the project")
    priority_field_id: Optional[str] = Field(None, description="The field ID for the priority column in the project")
    status_option_id: Optional[str] = Field(None, description="The option ID for the status value to set")
    priority_option_id: Optional[str] = Field(None, description="The option ID for priority value to set")

class AssignIssuesToProjectWorkflow(Workflow):
    """Workflow for assigning GitHub issues to a project."""
    __configuration: AssignIssuesToProjectWorkflowConfiguration
    
    def __init__(self, configuration: AssignIssuesToProjectWorkflowConfiguration):
        self.__configuration = configuration
        
        self.__github_integration = GithubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GithubGraphqlIntegration(self.__configuration.github_graphql_integration_config)
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="assign_issues_to_github_project",
            description="Assigns Open issues from repository to a GitHub project",
            func=lambda **kwargs: self.run(AssignIssuesToProjectWorkflowParameters(**kwargs)),
            args_schema=AssignIssuesToProjectWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/assign_issues_to_project")
        def assign_issues_to_project(parameters: AssignIssuesToProjectWorkflowParameters):
            return self.run(parameters)

    def run(self, parameters: AssignIssuesToProjectWorkflowParameters) -> list:
        # Get all issues from the repository
        issues = self.__github_integration.get_issues(parameters.repo_name, state=parameters.state)
        logger.debug(f"Issues fetched: {len(issues)}")

        # Get project node id
        organization = parameters.repo_name.split("/")[0]
        project_data : dict = self.__github_graphql_integration.get_project_node_id(organization, parameters.project_id)
        project_node_id = _.get(project_data, "data.organization.projectV2.id")
        logger.debug(f"Project node ID: {project_node_id}")
        
        assigned_issues = []
        for issue in issues:
            project_item = self.__github_graphql_integration.get_item_id_from_node_id(issue['node_id'])
            item_id = None
            for x in project_item.get("data").get("node").get("projectItems").get("nodes"):
                if x.get("project", {}).get("id") == project_node_id:
                    item_id = _.get(x, "id")
                    break
            logger.debug(f"Item ID: {item_id}")

            if item_id is None:
                # Add each issue to the project
                self.__github_graphql_integration.add_issue_to_project(
                    project_node_id=project_node_id,
                    issue_node_id=issue['node_id'],
                    status_field_id=parameters.status_field_id,
                    priority_field_id=parameters.priority_field_id,
                    status_option_id=parameters.status_option_id,
                    priority_option_id=parameters.priority_option_id
                )
                assigned_issues.append(issue)
                logger.debug(f"Assigned issue {issue['number']} to project {parameters.project_id}")
            else:
                logger.debug(f"Issue {issue['number']} already assigned to project {parameters.project_id}")

        return assigned_issues