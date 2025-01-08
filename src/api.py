from fastapi import FastAPI, APIRouter
from src import secret
import subprocess
# Foundation assistants
from src.assistants.foundation.SupportAssistant import create_support_assistant
from src.assistants.foundation.SupervisorAssistant import create_supervisor_agent
# Domain assistants
from src.assistants.domain.OpenDataAssistant import create_open_data_assistant
from src.assistants.domain.ContentAssistant import create_content_assistant
from src.assistants.domain.FinanceAssistant import create_finance_assistant
from src.assistants.domain.GrowthAssistant import create_growth_assistant
from src.assistants.domain.OperationsAssistant import create_operations_assistant
from src.assistants.domain.SalesAssistant import create_sales_assistant
# Pipelines
from src.data.pipelines.github.GithubIssuePipeline import GithubIssuePipeline, GithubIssuePipelineConfiguration
from src.data.pipelines.github.GithubIssuesPipeline import GithubIssuesPipeline, GithubIssuesPipelineConfiguration
from src.data.pipelines.github.GithubUserDetailsPipeline import GithubUserDetailsPipeline, GithubUserDetailsPipelineConfiguration
from src.integrations.GithubIntegration import GithubIntegrationConfiguration
from src.integrations.GithubGraphqlIntegration import GithubGraphqlIntegrationConfiguration
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService

def get_git_tag():
    try:
        tag = subprocess.check_output(["git", "describe", "--tags"]).strip().decode()
    except subprocess.CalledProcessError:
        tag = "v0.0.1"
    return tag

app = FastAPI(
    title="ABI API",
    description="API for ABI, your Artifical Business Intelligence",
    version=get_git_tag(),
    openapi_tags=[
        {
            "name": "Assistants",
            "description": "API endpoints for interacting with ABI's assistant/agents."
        },
        {
            "name": "Pipelines",
            "description": "API endpoints for interacting with ABI's pipelines."
        },
        {
            "name": "Workflows",
            "description": "API endpoints for interacting with ABI's workflows."
        },
        {
            "name": "Integrations",
            "description": "API endpoints for interacting with ABI's integrations."
        },
        {
            "name": "Ontology",
            "description": "API endpoints for interacting with ABI's ontology."
        },
        {
            "name": "Analytics",
            "description": "API endpoints for interacting with ABI's analytics."
        },
    ]
)

# Create Assistants API Router
assistants_router = APIRouter(
    prefix="/assistants", 
    tags=["Assistants"],
    responses={404: {"description": "Not found"}},
)

supervisor_agent = create_supervisor_agent()
supervisor_agent.as_api(
    assistants_router,
    route_name="supervisor",
    name="Supervisor Assistant",
    description="API endpoints to call the Supervisor assistant completion.",
    description_stream="API endpoints to call the Supervisor assistant stream completion."
)

support_agent = create_support_assistant()
support_agent.as_api(
    assistants_router,
    route_name="support",
    name="Support Assistant",
    description="API endpoints to call the Support assistant completion.",
    description_stream="API endpoints to call the Support assistant stream completion."
)

open_data_agent = create_open_data_assistant()
open_data_agent.as_api(
    assistants_router,
    route_name="open-data",
    name="Open Data Assistant",
    description="API endpoints to call the Open Data assistant completion.",
    description_stream="API endpoints to call the Open Data assistant stream completion."
)

content_agent = create_content_assistant()
content_agent.as_api(
    assistants_router,
    route_name="content",
    name="Content Assistant",
    description="API endpoints to call the Content assistant completion.",
    description_stream="API endpoints to call the Content assistant stream completion."
)

growth_agent = create_growth_assistant()
growth_agent.as_api(
    assistants_router,
    route_name="growth",
    name="Growth Assistant",
    description="API endpoints to call the Growth assistant completion.",
    description_stream="API endpoints to call the Growth assistant stream completion."
)

sales_agent = create_sales_assistant()
sales_agent.as_api(
    assistants_router,
    route_name="sales",
    name="Sales Assistant",
    description="API endpoints to call the Sales assistant completion.",
    description_stream="API endpoints to call the Sales assistant stream completion."
)

operations_agent = create_operations_assistant()
operations_agent.as_api(
    assistants_router,
    route_name="operations",
    name="Operations Assistant",
    description="API endpoints to call the Operations assistant completion.",
    description_stream="API endpoints to call the Operations assistant stream completion."
)

finance_agent = create_finance_assistant()
finance_agent.as_api(
    assistants_router,
    route_name="finance",
    name="Finance Assistant",
    description="API endpoints to call the Finance assistant completion.",
    description_stream="API endpoints to call the Finance assistant stream completion."
)

# Create Pipelines API Router
pipelines_router = APIRouter(
    prefix="/pipelines", 
    tags=["Pipelines"],
    responses={404: {"description": "Not found"}},
)

# Initialize services
ontology_store = OntologyStoreService(
    OntologyStoreService__SecondaryAdaptor__Filesystem(store_path="src/data/ontology-store")
)

github_issue_pipeline = GithubIssuePipeline(
    configuration=GithubIssuePipelineConfiguration(
        github_integration_config=GithubIntegrationConfiguration(access_token=secret.get("GITHUB_ACCESS_TOKEN")),
        github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get("GITHUB_ACCESS_TOKEN")),
        ontology_store=ontology_store
    )
)
github_issue_pipeline.as_api(pipelines_router)

github_issues_pipeline = GithubIssuesPipeline(
    configuration=GithubIssuesPipelineConfiguration(
        github_integration_config=GithubIntegrationConfiguration(access_token=secret.get("GITHUB_ACCESS_TOKEN")),
        github_graphql_integration_config=GithubGraphqlIntegrationConfiguration(access_token=secret.get("GITHUB_ACCESS_TOKEN")),
        ontology_store=ontology_store
    )
)
github_issues_pipeline.as_api(pipelines_router)

github_user_details_pipeline = GithubUserDetailsPipeline(
    configuration=GithubUserDetailsPipelineConfiguration(
        github_integration_config=GithubIntegrationConfiguration(access_token=secret.get("GITHUB_ACCESS_TOKEN")),
        ontology_store=ontology_store
    )
)
github_user_details_pipeline.as_api(pipelines_router)

# Include routers
app.include_router(assistants_router)
app.include_router(pipelines_router)

def root():
    return {"message": "Hello World"}

def api():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9879)