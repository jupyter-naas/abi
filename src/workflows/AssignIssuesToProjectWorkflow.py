from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional
from abi import logger
import pydash as _

@dataclass
class AssignIssuesToProjectWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for assigning GitHub issues to a project.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        github_graphql_integration_config: Configuration for GitHub GraphQL API
        repo_name: Repository name in format owner/repo
        project_id: Project number (from GitHub project URL)
        status_field_id: Field ID for status column
        priority_field_id: Field ID for priority column
        status_option_id: Option ID for status value
        priority_option_id: Option ID for priority value
    """
    github_integration_config: GithubIntegrationConfiguration
    github_graphql_integration_config: GithubGraphqlIntegrationConfiguration
    repo_name: str
    project_id: int
    state: str = "open"
    status_field_id: Optional[str] = None
    priority_field_id: Optional[str] = None
    status_option_id: Optional[str] = None
    priority_option_id: Optional[str] = None

class AssignIssuesToProjectWorkflow(Workflow):
    __configuration: AssignIssuesToProjectWorkflowConfiguration
    
    def __init__(self, configuration: AssignIssuesToProjectWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.__github_integration = GithubIntegration(self.__configuration.github_integration_config)
        self.__github_graphql_integration = GithubGraphqlIntegration(self.__configuration.github_graphql_integration_config)
    
    def run(self) -> str:
        # Get all issues from the repository
        issues = self.__github_integration.get_issues(self.__configuration.repo_name, state=self.__configuration.state)
        logger.debug(f"Issues fetched: {len(issues)}")

        # Get project node id
        organization = self.__configuration.repo_name.split("/")[0]
        project_data : dict = self.__github_graphql_integration.get_project_node_id(organization, self.__configuration.project_id)
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
                    status_field_id=self.__configuration.status_field_id,
                    priority_field_id=self.__configuration.priority_field_id,
                    status_option_id=self.__configuration.status_option_id,
                    priority_option_id=self.__configuration.priority_option_id
                )
                assigned_issues.append(issue)
                logger.debug(f"Assigned issue {issue['number']} to project {self.__configuration.project_id}")
            else:
                logger.debug(f"Issue {issue['number']} already assigned to project {self.__configuration.project_id}")

        return assigned_issues

def api():
    import fastapi
    import uvicorn
    
    app = fastapi.FastAPI()
    
    @app.post("/assign_issues_to_project")
    def assign_issues_to_project(
        repo_name: str, 
        project_id: int,
        status_field_id: Optional[str] = None,
        priority_field_id: Optional[str] = None,
        status_option_id: Optional[str] = None,
        priority_option_id: Optional[str] = None
    ):
        configuration = AssignIssuesToProjectWorkflowConfiguration(
            github_integration_config=GithubIntegrationConfiguration(
                access_token=secret.get('GITHUB_ACCESS_TOKEN')
            ),
            github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(
                access_token=secret.get('GITHUB_ACCESS_TOKEN')
            ),
            repo_name=repo_name,
            project_id=project_id,
            status_field_id=status_field_id,
            priority_field_id=priority_field_id,
            status_option_id=status_option_id,
            priority_option_id=priority_option_id
        )
        workflow = AssignIssuesToProjectWorkflow(configuration)
        return workflow.run()
    
    uvicorn.run(app, host="0.0.0.0", port=9879)

def main():
    configuration = AssignIssuesToProjectWorkflowConfiguration(
        github_integration_config=GithubIntegrationConfiguration(
            access_token=secret.get('GITHUB_ACCESS_TOKEN')
        ),
        github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(
            access_token=secret.get('GITHUB_ACCESS_TOKEN')
        ),
        repo_name="owner/repo",
        project_id=1
    )
    workflow = AssignIssuesToProjectWorkflow(configuration)
    result = workflow.run()
    print(result)

def as_tool():
    from langchain_core.tools import StructuredTool
    
    class AssignIssuesToProjectSchema(BaseModel):
        repo_name: str = Field(..., description="The repository name in format owner/repo")
        project_id: int = Field(..., description="The project number in GitHub (from Project URL)")
        status_field_id: Optional[str] = Field(None, description="The field ID for the status column in the project")
        priority_field_id: Optional[str] = Field(None, description="The field ID for the priority column in the project")
        status_option_id: Optional[str] = Field(None, description="The option ID for the status value to set")
        priority_option_id: Optional[str] = Field(None, description="The option ID for priority value to set")
    
    def assign_issues_tool(
        repo_name: str,
        project_id: int,
        status_field_id: Optional[str] = None,
        priority_field_id: Optional[str] = None,
        status_option_id: Optional[str] = None,
        priority_option_id: Optional[str] = None
    ):
        configuration = AssignIssuesToProjectWorkflowConfiguration(
            github_integration_config=GithubIntegrationConfiguration(
                access_token=secret.get('GITHUB_ACCESS_TOKEN')
            ),
            github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(
                access_token=secret.get('GITHUB_ACCESS_TOKEN')
            ),
            repo_name=repo_name,
            project_id=project_id,
            status_field_id=status_field_id,
            priority_field_id=priority_field_id,
            status_option_id=status_option_id,
            priority_option_id=priority_option_id
        )
        workflow = AssignIssuesToProjectWorkflow(configuration)
        return workflow.run()
    
    return StructuredTool(
        name="assign_issues_to_github_project",
        description="Assigns Open issues from repository to a GitHub project",
        func=assign_issues_tool,
        args_schema=AssignIssuesToProjectSchema
    )

if __name__ == "__main__":
    main() 