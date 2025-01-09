from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.openapi.utils import get_openapi
from fastapi.security.oauth2 import OAuth2
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from fastapi.security.utils import get_authorization_scheme_param
from src import secret
import subprocess
import os 
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

TITLE = "ABI API"
DESCRIPTION = "API for ABI, your Artifical Business Intelligence"

# Init API
app = FastAPI(title=TITLE)

# Mount the static directory
app.mount("/static", StaticFiles(directory="assets"), name="static")

# Authentication
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Annotated

# Custom OAuth2 class that accepts query parameter
class OAuth2QueryBearer(OAuth2):
    def __init__(
        self,
        tokenUrl: str,
        scheme_name: str = None,
        auto_error: bool = True,
    ):
        flows = OAuthFlowsModel(password={"tokenUrl": tokenUrl})
        super().__init__(flows=flows, scheme_name=scheme_name, auto_error=auto_error)

    async def __call__(self, token: str = None, authorization: str = Header(None)) -> str:
        # Check header first
        if authorization:
            scheme, header_token = get_authorization_scheme_param(authorization)
            if scheme.lower() == "bearer":
                return header_token
        
        # Then check query parameter
        if token:
            return token
            
        # No token found in either place
        if self.auto_error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None

# Replace the existing oauth2_scheme with:
oauth2_scheme = OAuth2QueryBearer(tokenUrl="token")

# Update the token validation dependency
async def is_token_valid(token: str = Depends(oauth2_scheme)):
    if token != os.environ.get("ABI_API_KEY"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], include_in_schema=False):
    if form_data.password != "abi":
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": "abi", "token_type": "bearer"}

# Create Assistants API Router
assistants_router = APIRouter(
    prefix="/assistants", 
    tags=["Assistants"],
    responses={404: {"description": "Not found"}},
    dependencies=[Depends(is_token_valid)]  # Apply token verification
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
content_agent.as_api(assistants_router)

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
    dependencies=[Depends(is_token_valid)]  # Apply token verification
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

def get_git_tag():
    try:
        tag = subprocess.check_output(["git", "describe", "--tags"]).strip().decode()
    except subprocess.CalledProcessError:
        tag = "v0.0.1"
    return tag

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="ABI API",
        description="API for ABI, your Artifical Business Intelligence",
        version=get_git_tag(),
        routes=app.routes,
        tags=[
            {
                "name": "Overview",
                "description": "The ABI (Artificial Business Intelligence) API allows users and applications to interact with ABI's capabilities for business process automation and intelligence. This document describes the current version of the ABI API, which provides access to assistants, pipelines, workflows, integrations, ontology management and analytics features."
            },
            {
                "name": "Data Access",
                "description": "Data access is currently configured using secrets (API keys, credentials) set up in the GitHub project settings. In an upcoming update, ABI will integrate with the Naas platform to securely access user-specific secrets and credentials."
            },
            {
                "name": "Authentication",
                "description": "Authentication uses a Bearer token that can be provided either in the Authorization header (e.g. 'Authorization: Bearer <token>') or as a query parameter (e.g. '?token=<token>').\nThe token must match the ABI_API_KEY environment variable."
            },
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
    openapi_schema["info"]["x-logo"] = {
        "url": "/static/logo.png",
        "altText": "ABI Logo"
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root():
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <title>ABI API</title>
            <link rel="icon" type="image/x-icon" href="/static/favicon.ico">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #000000;
                    color: white;
                }
                .logo {
                    width: 200px;
                    margin-bottom: 20px;
                }
                h1 {
                    font-size: 48px;
                    margin-bottom: 40px;
                }
                .buttons {
                    display: flex;
                    gap: 20px;
                }
                a {
                    padding: 12px 24px;
                    font-size: 18px;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    text-decoration: none;
                    color: white;
                    background-color: #007bff;
                    transition: background-color 0.2s;
                }
                a:hover {
                    background-color: #0056b3;
                }
            </style>
        </head>
        <body>
            <img src="/static/logo.png" alt="Naas Logo" class="logo">
            <h1>Welcome to ABI API!</h1>
            <p>ABI API is a tool that allows you to interact with ABI's capabilities for business process automation and intelligence.</p>
            <div class="buttons">
                <a href="/redoc">Go to Documentation</a>
            </div>
        </body>
    </html>
    """

def api():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9879)
