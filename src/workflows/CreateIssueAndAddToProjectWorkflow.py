from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from src import secret
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from typing import Optional, List
from abi import logger
import pydash as _

@dataclass
class CreateIssueAndAddToProjectWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for creating GitHub issues and adding them to projects.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
        repo_name: Repository name in format owner/repo
        issue_title: Title of the issue
        issue_body: Body content of the issue
        project_id: Project number (from GitHub project URL)
        assignees: List of assignees
        labels: List of labels
        status_field_id: Field ID for status column
        priority_field_id: Field ID for priority column
        status_option_id: Option ID for status value
        priority_option_id: Option ID for priority value
    """
    github_integration_config: GithubIntegrationConfiguration
    github_graphql_integration_config: GithubGraphqlIntegrationConfiguration
    repo_name: str
    issue_title: str
    issue_body: str
    project_id: int = 0
    assignees: Optional[List[str]] = field(default_factory=list)
    labels: Optional[List[str]] = field(default_factory=list)
    status_field_id: Optional[str] = None
    priority_field_id: Optional[str] = None
    status_option_id: Optional[str] = None
    priority_option_id: Optional[str] = None

class CreateIssueAndAddToProjectWorkflow(Workflow):
    
    __configuration: CreateIssueAndAddToProjectWorkflowConfiguration
    
    def __init__(self, configuration: CreateIssueAndAddToProjectWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        self.__github_integration = GithubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GithubGraphqlIntegration(self.__configuration.github_graphql_integration_config)

    def run(self) -> str:
        # Create an issue
        issue = self.__github_integration.create_issue(
            repo_name=self.__configuration.repo_name,
            title=self.__configuration.issue_title,
            body=self.__configuration.issue_body,
            assignees=self.__configuration.assignees,
            labels=self.__configuration.labels
        )
        
        # Get project node id
        if self.__configuration.project_id != 0:
            organization = self.__configuration.repo_name.split("/")[0]
            project_data : dict = self.__github_graphql_integration.get_project_node_id(organization, self.__configuration.project_id) # type: ignore
            project_node_id = _.get(project_data, "data.organization.projectV2.id")
            logger.debug(f"Project node ID: {project_node_id}")

            # Add the issue to a project
            issue_node_id = issue['node_id']
            logger.debug(f"Issue node ID: {issue_node_id}")
            self.__github_graphql_integration.add_issue_to_project(
                project_node_id=project_node_id,
                issue_node_id=issue_node_id,
                status_field_id=self.__configuration.status_field_id,
                priority_field_id=self.__configuration.priority_field_id,
                status_option_id=self.__configuration.status_option_id,
                priority_option_id=self.__configuration.priority_option_id
            )
        else:
            logger.debug("No project ID provided, skipping project data")
        
        return f"Issue '{self.__configuration.issue_title}' created and added to project: {issue}."
        


def api():
    import fastapi
    import uvicorn
    
    app = fastapi.FastAPI()
    
    @app.post("/create_issue_and_add_to_project")
    def create_issue_and_add_to_project(repo_name: str, issue_title: str, issue_body: str, project_id: str, status_field_id: str, priority_field_id: str, status_option_id: str, priority_option_id: str):
        configuration = CreateIssueAndAddToProjectWorkflowConfiguration(
            github_integration_config=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            repo_name=repo_name,
            issue_title=issue_title,
            issue_body=issue_body,
            project_id=project_id,
            status_field_id=status_field_id,
            priority_field_id=priority_field_id,
            status_option_id=status_option_id,
            priority_option_id=priority_option_id
        )
    
        workflow = CreateIssueAndAddToProjectWorkflow(configuration)
        
        return workflow.run()
        
    uvicorn.run(app, host="0.0.0.0", port=9878)

def main():
    configuration = CreateIssueAndAddToProjectWorkflowConfiguration(
        github_integration_config=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
        github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
        repo_name="owner/repo",
        issue_title="New Issue",
        issue_body="This is a new issue.",
        project_id="project_id",
        assignees=["assignee1", "assignee2"],
        labels=["label1", "label2"],
        status_field_id="status_field_id",
        priority_field_id="priority_field_id",
        status_option_id="status_option_id",
        priority_option_id="priority_option_id"
    )
    
    workflow = CreateIssueAndAddToProjectWorkflow(configuration)
    result = workflow.run()
    print(result)

def as_tool():
    from langchain_core.tools import StructuredTool

    class CreateIssueAndAddToProjectSchema(BaseModel):
        repo_name: str = Field(..., description="The repository name in format owner/repo")
        issue_title: str = Field(..., description="The title of the issue to create")
        issue_body: str = Field(..., description="The description of the issue")
        project_id: int = Field(..., description="The project number in GitHub (Project URL)")
        assignees: Optional[List[str]] = Field(None, description="The assignees of the issue")
        labels: Optional[List[str]] = Field(None, description="The labels of the issue")
        status_field_id: Optional[str] = Field(None, description="The field ID for the status column in the project")
        priority_field_id: Optional[str] = Field(None, description="The field ID for the priority column in the project")
        status_option_id: Optional[str] = Field(None, description="The option ID for the status value to set")
        priority_option_id: Optional[str] = Field(None, description="The option ID for priority")

    def create_issue_tool(
        repo_name: str, 
        issue_title: str, 
        issue_body: str, 
        project_id: int,
        assignees: Optional[List[str]] = [],
        labels: Optional[List[str]] = [],
        status_field_id: Optional[str] = None,
        priority_field_id: Optional[str] = None,
        status_option_id: Optional[str] = None,
        priority_option_id: Optional[str] = None
    ):
        configuration = CreateIssueAndAddToProjectWorkflowConfiguration(
            github_integration_config=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            repo_name=repo_name,
            issue_title=issue_title,
            issue_body=issue_body,
            project_id=project_id,
            assignees=assignees,
            labels=labels,
            status_field_id=status_field_id,
            priority_field_id=priority_field_id,
            status_option_id=status_option_id,
            priority_option_id=priority_option_id
        )
        workflow = CreateIssueAndAddToProjectWorkflow(configuration)
        return workflow.run()

    return StructuredTool(
        name="create_github_issue",
        description="Creates a GitHub issue and optionally adds it to a project with status and priority settings",
        func=create_issue_tool,
        args_schema=CreateIssueAndAddToProjectSchema
    )

if __name__ == "__main__":
    main() 