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
# Docs
from src.openapi_doc import TAGS_METADATA, API_LANDING_HTML
from src import config

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

# Create Agents API Router
agents_router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
    responses={401: {"description": "Unauthorized"}},
    dependencies=[Depends(is_token_valid)]  # Apply token verification
)

# Create Pipelines API Router
pipelines_router = APIRouter(
    prefix="/pipelines", 
    tags=["Pipelines"],
    responses={401: {"description": "Unauthorized"}},
    dependencies=[Depends(is_token_valid)]  # Apply token verification
)

# Create Pipelines API Router
workflows_router = APIRouter(
    prefix="/workflows", 
    tags=["Workflows"],
    responses={401: {"description": "Unauthorized"}},
    dependencies=[Depends(is_token_valid)]  # Apply token verification
)

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

# Automatic loading of agents from modules
from src.__modules__ import get_modules

for module in get_modules():
    for agent in module.agents:
        logger.debug(f"Loading agent: {agent.name}")
        agent.as_api(agents_router)

# Include routers
app.include_router(agents_router)
app.include_router(pipelines_router)
app.include_router(workflows_router)

def api():
    import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=9879, reload=True)
    uvicorn.run('src.api:app', host="0.0.0.0", port=9879, reload=True)

# @app.post("/telegram")
# async def telegram(req: Request):
#     data = await req.json()
#     chat_id = data['message']['chat']['id']
#     text = data['message']['text']
    
#     requests.get(f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_KEY')}/sendMessage?chat_id={chat_id}&text={text}")

#     return data