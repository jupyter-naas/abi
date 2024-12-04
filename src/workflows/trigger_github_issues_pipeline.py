from src.data.pipelines.github.github_issues_pipeline import GithubIssuesPipeline, GithubIssuesPipelineConfiguration
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from abi.workflow import Workflow, WorkflowConfiguration
from dataclasses import dataclass
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from src import secret

@dataclass
class GithubIssuesWorkflowConfiguration(WorkflowConfiguration):
    integration_configuration: GithubIntegrationConfiguration
    pipeline_configuration: GithubIssuesPipelineConfiguration

class GithubIssuesWorkflow(Workflow):
    
    __configuration: GithubIssuesWorkflowConfiguration
    
    def __init__(self, configuration: GithubIssuesWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        self.__ontology_store_adaptor = OntologyStoreService__SecondaryAdaptor__Filesystem(secret.get('ONTOLOGY_STORE_PATH'))
        self.__ontology_store = OntologyStoreService(self.__ontology_store_adaptor)
        self.__github_integration = GithubIntegration(self.__configuration.integration_configuration)
        self.__github_issues_pipeline = GithubIssuesPipeline(self.__github_integration, self.__ontology_store, self.__configuration.pipeline_configuration)

    def run(self) -> str:
        graph = self.__github_issues_pipeline.run()
        return graph.serialize(format="turtle")

def api():
    import fastapi
    import uvicorn
    from src import secret
    
    app = fastapi.FastAPI()
    
    @app.get("/github_issues")
    def github_issues(repo_name: str):
        
        configuration : GithubIssuesWorkflowConfiguration = GithubIssuesWorkflowConfiguration(
            integration_configuration=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            pipeline_configuration=GithubIssuesPipelineConfiguration(repo_name=repo_name)
        )
    
        workflow = GithubIssuesWorkflow(configuration)
        
        return workflow.run()
        
    
    # Start API
    uvicorn.run(app, host="0.0.0.0", port=9878)
    
def main():
    from src import secret
    
    configuration : GithubIssuesWorkflowConfiguration = GithubIssuesWorkflowConfiguration(
        integration_configuration=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
        pipeline_configuration=GithubIssuesPipelineConfiguration(repo_name="example/repo")
    )
    
    workflow = GithubIssuesWorkflow(configuration)
    result = workflow.run()
    print(result)

def as_tool():
    from src import secret
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    class GithubIssuesInput(BaseModel):
        repo_name: str = Field(description="(Mandatory) The repository name to fetch issues from")
    
    def github_issues(repo_name: str):
        configuration : GithubIssuesWorkflowConfiguration = GithubIssuesWorkflowConfiguration(
            integration_configuration=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            pipeline_configuration=GithubIssuesPipelineConfiguration(github_repository=repo_name)
        )
        workflow = GithubIssuesWorkflow(configuration)
        return workflow.run()
    
    return StructuredTool.from_function(
        name="load_github_issues", 
        description="Fetch issues from a GitHub repository.", 
        func=github_issues, 
        args_schema=GithubIssuesInput
    )

if __name__ == "__main__":
    main()