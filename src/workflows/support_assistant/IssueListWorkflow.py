from abi.workflow import Workflow, WorkflowConfiguration
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src import secret
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from abi import logger

@dataclass
class IssueListWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for listing GitHub issues.
    
    Attributes:
        github_integration_config: Configuration for GitHub REST API
        repo_name: Repository name in format owner/repo (defaults to "jupyter-naas/abi")
        state: Filter issues by state (defaults to "open")
        limit: Maximum number of issues to return (defaults to -1, meaning all issues)
    """
    github_integration_config: GithubIntegrationConfiguration
    repo_name: str = "jupyter-naas/support"
    state: str = "open"
    limit: int = -1

class IssueListWorkflow(Workflow):
    __configuration: IssueListWorkflowConfiguration
    
    def __init__(self, configuration: IssueListWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__github_integration = GithubIntegration(self.__configuration.github_integration_config)

    def run(self) -> List[Dict]:
        # Get issues using the GitHub integration
        issues = self.__github_integration.get_issues(
            repo_name=self.__configuration.repo_name,
            state=self.__configuration.state,
            limit=self.__configuration.limit
        )
        logger.info(f"Found {len(issues)} issues:")
        return [f"#{issue['number']} - {issue['title']}: {issue['body']}" for issue in issues]

def api():
    import fastapi
    import uvicorn
    
    app = fastapi.FastAPI()
    
    @app.get("/list_issues")
    def list_issues(
        state: str = "open",
        limit: int = -1
    ):
        configuration = IssueListWorkflowConfiguration(
            github_integration_config=GithubIntegrationConfiguration(
                access_token=secret.get('GITHUB_ACCESS_TOKEN')
            ),
            state=state,
            limit=limit
        )
        workflow = IssueListWorkflow(configuration)
        return workflow.run()
    
    uvicorn.run(app, host="0.0.0.0", port=9879)

def main():
    configuration = IssueListWorkflowConfiguration(
        github_integration_config=GithubIntegrationConfiguration(
            access_token=secret.get('GITHUB_ACCESS_TOKEN')
        )
    )
    
    workflow = IssueListWorkflow(configuration)
    issues = workflow.run()
    print(f"Found {len(issues)} issues:")
    for issue in issues:
        print(f"#{issue['number']} - {issue['title']}")

def as_tool():
    from langchain_core.tools import StructuredTool
    
    class IssueListSchema(BaseModel):
        pass

    def issue_list_tool(
        state: str = "open",
        limit: int = -1
    ):
        configuration = IssueListWorkflowConfiguration(
            github_integration_config=GithubIntegrationConfiguration(
                access_token=secret.get('GITHUB_ACCESS_TOKEN')
            ),
            state=state,
            limit=limit
        )
        workflow = IssueListWorkflow(configuration)
        return workflow.run()

    return StructuredTool(
        name="list_github_issues",
        description="Lists GitHub issues from the GitHub repository.",
        func=lambda **kwargs: issue_list_tool(**kwargs),
        args_schema=IssueListSchema
    )

if __name__ == "__main__":
    main() 