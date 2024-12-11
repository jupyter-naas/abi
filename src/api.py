from fastapi import FastAPI, APIRouter
from src.data.pipelines.github.GithubIssuePipeline import GithubIssuePipeline, GithubIssuePipelineConfiguration
from src.data.pipelines.github.GithubIssuesPipeline import GithubIssuesPipeline, GithubIssuesPipelineConfiguration
from src.data.pipelines.github.GithubUserDetailsPipeline import GithubUserDetailsPipeline, GithubUserDetailsPipelineConfiguration
from src.integrations.GithubIntegration import GithubIntegration, GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegration, GithubGraphqlIntegrationConfiguration
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from src import secret

app = FastAPI()

pipelines_router = APIRouter(prefix="/pipelines")

#Sub router for github pipelines
github_router = APIRouter(prefix="/github")

# Initialize services
github_integration = GithubIntegration(
    GithubIntegrationConfiguration(access_token=secret.get("GITHUB_ACCESS_TOKEN"))
)

github_graphql_integration = GithubGraphqlIntegration(
    GithubGraphqlIntegrationConfiguration(access_token=secret.get("GITHUB_ACCESS_TOKEN"))
)

ontology_store = OntologyStoreService(
    OntologyStoreService__SecondaryAdaptor__Filesystem(store_path="src/data/ontology-store")
)

# Initialize pipelines
github_issue_pipeline = GithubIssuePipeline(
    configuration=GithubIssuePipelineConfiguration(
        github_integration=github_integration,
        github_graphql_integration=github_graphql_integration,
        ontology_store=ontology_store
    )
)

github_issues_pipeline = GithubIssuesPipeline(
    configuration=GithubIssuesPipelineConfiguration(
        github_integration=github_integration,
        github_graphql_integration=github_graphql_integration,
        ontology_store=ontology_store
    )
)

github_user_details_pipeline = GithubUserDetailsPipeline(
    configuration=GithubUserDetailsPipelineConfiguration(
        github_integration=github_integration
    )
)

# Register pipeline APIs
github_issue_pipeline.as_api(pipelines_router)
github_issues_pipeline.as_api(pipelines_router)
github_user_details_pipeline.as_api(pipelines_router)
pipelines_router.include_router(github_router)

# Include router
app.include_router(pipelines_router)

@app.get("/")
def root():
    return {"message": "Hello World"}

def api():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9879)
