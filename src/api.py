from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.openapi.utils import get_openapi
from fastapi.security.oauth2 import OAuth2
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from fastapi.security.utils import get_authorization_scheme_param
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from src import secret
import subprocess
import os
from abi import logger
# Authentication
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Annotated
# Foundation assistants
from src.core.assistants.foundation.SupportAssistant import create_support_agent
from src.core.assistants.foundation.SupervisorAssistant import create_supervisor_agent
# Domain assistants
from src.core.assistants.domain.OpenDataAssistant import create_open_data_agent
from src.core.assistants.domain.ContentAssistant import create_content_agent
from src.core.assistants.domain.FinanceAssistant import create_finance_agent
from src.core.assistants.domain.GrowthAssistant import create_growth_agent
from src.core.assistants.domain.OperationsAssistant import create_operations_agent
from src.core.assistants.domain.SalesAssistant import create_sales_agent
# Integrations
from src.core.assistants.expert.integrations.PowerPointAssistant import create_powerpoint_agent
from src.core.assistants.expert.integrations.NaasAssistant import create_naas_agent
# Pipelines
from src.core.pipelines.github.GithubIssuePipeline import GithubIssuePipeline, GithubIssuePipelineConfiguration
from src.core.pipelines.github.GithubIssuesPipeline import GithubIssuesPipeline, GithubIssuesPipelineConfiguration
from src.core.pipelines.github.GithubUserDetailsPipeline import GithubUserDetailsPipeline, GithubUserDetailsPipelineConfiguration
from src.core.integrations.GithubIntegration import GithubIntegrationConfiguration
from src.core.integrations.GithubGraphqlIntegration import GithubGraphqlIntegrationConfiguration
from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
# Docs
from src.openapi_doc import TAGS_METADATA, API_LANDING_HTML
from src import config
import requests

# Init API
TITLE = config.api_title
DESCRIPTION = config.api_description
app = FastAPI(title=TITLE, docs_url=None, redoc_url=None)

# Set logo path
logo_path = config.logo_path
logo_name = os.path.basename(logo_path)

# Set favicon path
favicon_path = config.favicon_path
favicon_name = os.path.basename(favicon_path)

# Mount the static directory
app.mount("/static", StaticFiles(directory="assets"), name="static")

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


@app.post("/token", include_in_schema=False)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if form_data.password != "abi":
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    return {"access_token": "abi", "token_type": "bearer"}

# Create Assistants API Router
assistants_router = APIRouter(
    prefix="/assistants",
    tags=["Assistants"],
    responses={401: {"description": "Unauthorized"}},
    dependencies=[Depends(is_token_valid)]  # Apply token verification
)

supervisor_agent = create_supervisor_agent()
supervisor_agent.as_api(assistants_router)

support_agent = create_support_agent()
support_agent.as_api(assistants_router)

open_data_agent = create_open_data_agent()
open_data_agent.as_api(assistants_router)

content_agent = create_content_agent()
content_agent.as_api(assistants_router)

growth_agent = create_growth_agent()
growth_agent.as_api(assistants_router)

sales_agent = create_sales_agent()
sales_agent.as_api(assistants_router)

operations_agent = create_operations_agent()
operations_agent.as_api(assistants_router)

finance_agent = create_finance_agent()
finance_agent.as_api(assistants_router)

naas_agent = create_naas_agent()
naas_agent.as_api(assistants_router)

powerpoint_agent = create_powerpoint_agent()
powerpoint_agent.as_api(assistants_router)

# Create Pipelines API Router
pipelines_router = APIRouter(
    prefix="/pipelines", 
    tags=["Pipelines"],
    responses={401: {"description": "Unauthorized"}},
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
        title=TITLE,
        description=DESCRIPTION,
        version=get_git_tag(),
        routes=app.routes,
        tags=TAGS_METADATA
    )
    openapi_schema["info"]["x-logo"] = {
        "url": f"/static/{logo_name}",
        "altText": "Logo"
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/docs", include_in_schema=False)
def overridden_swagger():
	return get_swagger_ui_html(openapi_url="/openapi.json", title=TITLE, swagger_favicon_url=f"/static/{favicon_name}")

@app.get("/redoc", include_in_schema=False)
def overridden_redoc():
	return get_redoc_html(openapi_url="/openapi.json", title=TITLE, redoc_favicon_url=f"/static/{favicon_name}")

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root():
    return API_LANDING_HTML.replace("[TITLE]", TITLE).replace("[LOGO_NAME]", logo_name)

# @app.post("/telegram")
# async def telegram(req: Request):
#     data = await req.json()
#     chat_id = data['message']['chat']['id']
#     text = data['message']['text']
    
#     requests.get(f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_KEY')}/sendMessage?chat_id={chat_id}&text={text}")

#     return data

def api():
    import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=9879, reload=True)
    uvicorn.run('src.api:app', host="0.0.0.0", port=9879, reload=True)
