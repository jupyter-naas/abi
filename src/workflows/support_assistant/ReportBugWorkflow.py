from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from src import config
from dataclasses import dataclass, field
from pydantic import Field
from typing import Optional, List
from abi import logger
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool


@dataclass
class ReportBugWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for creating new bug GitHub issues and adding them to project.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
    """
    github_integration_config: GithubIntegrationConfiguration
    github_graphql_integration_config: GithubGraphqlIntegrationConfiguration


class ReportBugWorkflowParameters(WorkflowParameters):
    """Parameters for ReportBugWorkflow execution.
    
    Attributes:
        issue_title: Title of the bug report
        issue_body: Body content of the bug report
    """
    issue_title: str = Field(..., description="The title of the bug report")
    issue_body: str = Field(..., description="The description of the bug, including steps to reproduce")

class ReportBugWorkflow(Workflow):
    """Workflow for creating a new bug GitHub issue and adding it to project."""
    __configuration: ReportBugWorkflowConfiguration
    
    def __init__(self, configuration: ReportBugWorkflowConfiguration):
        self.__configuration = configuration
        self.__github_integration = GithubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GithubGraphqlIntegration(self.__configuration.github_graphql_integration_config)

    def run(self, parameters: ReportBugWorkflowParameters) -> str:
        repo_name = config.github_support_repository
        project_node_id = "PVT_kwDOBESWNM4AKRt3"
        assignees = []
        labels = ["bug"]
        status_field_id = "PVTSSF_lADOBESWNM4AKRt3zgGZRV8"
        priority_field_id = "PVTSSF_lADOBESWNM4AKRt3zgGac0g"
        status_option_id = "97363483"
        priority_option_id = "4fb76f2d"

        # Create an issue
        issue = self.__github_integration.create_issue(
            repo_name=repo_name,
            title=parameters.issue_title,
            body=parameters.issue_body,
            labels=labels,
            assignees=assignees
        )
        
        # Add the issue to project using direct project_node_id
        issue_node_id = issue['node_id']
        logger.debug(f"Issue node ID: {issue_node_id}")
        self.__github_graphql_integration.add_issue_to_project(
            project_node_id=project_node_id,
            issue_node_id=issue_node_id,
            status_field_id=status_field_id,
            priority_field_id=priority_field_id,
            status_option_id=status_option_id,
            priority_option_id=priority_option_id
        )
        
        return f"Bug Report '{parameters.issue_title}' created and added to project: {issue}."
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [StructuredTool(
            name="create_bug_report",
            description="Create or post a bug report for the support assistant.",
            func=lambda **kwargs: self.run(ReportBugWorkflowParameters(**kwargs)),
            args_schema=ReportBugWorkflowParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this workflow to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/report_bug")
        def report_bug(parameters: ReportBugWorkflowParameters):
            return self.run(parameters)