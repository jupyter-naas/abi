from src.data.pipelines.github.github_user_details_pipeline import GithubUserDetailsPipeline, GithubUserDetailsPipelineConfiguration
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from abi.workflow import Workflow, WorkflowConfiguration
from dataclasses import dataclass

@dataclass
class ingestGithubUserWorkflowConfiguration(WorkflowConfiguration):
    integration_configuration: GithubIntegrationConfiguration
    pipeline_configuration: GithubUserDetailsPipelineConfiguration

class ingestGithubUserWorkflow(Workflow):
    
    __configuration: ingestGithubUserWorkflowConfiguration
    
    def __init__(self, configuration: ingestGithubUserWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

        self.__github_integration = GithubIntegration(self.__configuration.integration_configuration)
        self.__github_user_details_pipeline = GithubUserDetailsPipeline(self.__github_integration, self.__configuration.pipeline_configuration)

    def run(self) -> str:
        graph = self.__github_user_details_pipeline.run()
        
        return graph.serialize(format="turtle")


def api():
    import fastapi
    import uvicorn
    from src import secret
    
    app = fastapi.FastAPI()
    
    @app.get("/ingest_github_user")
    def ingest_github_user(github_username: str):
        
        configuration : ingestGithubUserWorkflowConfiguration = ingestGithubUserWorkflowConfiguration(
            integration_configuration=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            pipeline_configuration=GithubUserDetailsPipelineConfiguration(github_username=github_username)
        )
    
        workflow = ingestGithubUserWorkflow(configuration)
        
        return workflow.run()
        
    
    # Start API
    uvicorn.run(app, host="0.0.0.0", port=9876)
    
def main():
    from src import secret
    
    configuration : ingestGithubUserWorkflowConfiguration = ingestGithubUserWorkflowConfiguration(
        integration_configuration=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
        pipeline_configuration=GithubUserDetailsPipelineConfiguration(github_username="Dr0p42")
    )
    
    workflow = ingestGithubUserWorkflow(configuration)
    turtle = workflow.run()
    print(turtle)

def as_tool():
    from src import secret
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    class IngestGithubUserInput(BaseModel):
        github_username: str = Field(description="The github username to ingest")
    
    def ingest_github_user(github_username: str):
        configuration : ingestGithubUserWorkflowConfiguration = ingestGithubUserWorkflowConfiguration(
            integration_configuration=GithubIntegrationConfiguration(access_token=secret.get('GITHUB_ACCESS_TOKEN')),
            pipeline_configuration=GithubUserDetailsPipelineConfiguration(github_username=github_username)
        )
        workflow = ingestGithubUserWorkflow(configuration)
        return workflow.run()
    
    return StructuredTool.from_function(name="ingest_github_user", description="Get github user details. Only works for users and organizations, not repositories!!", func=ingest_github_user, args_schema=IngestGithubUserInput)

if __name__ == "__main__":
    main()