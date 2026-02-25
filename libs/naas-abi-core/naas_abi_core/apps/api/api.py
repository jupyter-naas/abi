import os
import subprocess
from importlib.resources import files
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.models import OAuthFlowPassword
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse

# Authentication
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.security.oauth2 import OAuth2
from fastapi.security.utils import get_authorization_scheme_param
from fastapi.staticfiles import StaticFiles
from naas_abi_core import logger

# Docs
from naas_abi_core.apps.api.openapi_doc import API_LANDING_HTML, TAGS_METADATA
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    ApiConfiguration,
    EngineConfiguration,
)


def _load_api_runtime_configuration() -> ApiConfiguration:
    try:
        return EngineConfiguration.load_configuration().api
    except Exception as exc:
        logger.warning(
            f"Failed to load API runtime configuration from engine configuration: {exc}"
        )
        return ApiConfiguration()


class LazyEngine:
    def __init__(self):
        self._engine: Engine | None = None

    def get(self) -> Engine:
        if self._engine is None:
            runtime_engine = Engine()
            runtime_engine.load()
            self._engine = runtime_engine
        return self._engine

    def __getattr__(self, name: str):
        return getattr(self.get(), name)


engine = LazyEngine()
api_runtime_configuration = _load_api_runtime_configuration()

# Init API
TITLE = api_runtime_configuration.title
DESCRIPTION = api_runtime_configuration.description
app = FastAPI(title=TITLE, docs_url=None, redoc_url=None)

# Set logo path
logo_path = api_runtime_configuration.logo_path
logo_name = os.path.basename(logo_path)

# Set favicon path
favicon_path = api_runtime_configuration.favicon_path
favicon_name = os.path.basename(favicon_path)

origins = api_runtime_configuration.cors_origins

logger.debug(f"CORS origins: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


static_dir = os.path.join(os.path.dirname(str(files("naas_abi_core"))), "assets")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Custom OAuth2 class that accepts query parameter
class OAuth2QueryBearer(OAuth2):
    def __init__(
        self,
        tokenUrl: str,
        scheme_name: Optional[str] = None,
        auto_error: bool = True,
    ):
        flows = OAuthFlowsModel(password=OAuthFlowPassword(tokenUrl=tokenUrl))
        super().__init__(flows=flows, scheme_name=scheme_name, auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[str]:
        authorization = request.headers.get("Authorization")
        # Check header first
        if authorization:
            scheme, header_token = get_authorization_scheme_param(authorization)
            if scheme.lower() == "bearer" and header_token:
                return header_token

        # Then check query parameter
        query_token = request.query_params.get("token")
        if query_token:
            return query_token

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
    dependencies=[Depends(is_token_valid)],  # Apply token verification
)

# Create Pipelines API Router
pipelines_router = APIRouter(
    prefix="/pipelines",
    tags=["Pipelines"],
    responses={401: {"description": "Unauthorized"}},
    dependencies=[Depends(is_token_valid)],  # Apply token verification
)

# Create Pipelines API Router
workflows_router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"],
    responses={401: {"description": "Unauthorized"}},
    dependencies=[Depends(is_token_valid)],  # Apply token verification
)


def get_git_tag():
    try:
        tag = subprocess.check_output(["git", "describe", "--tags"]).strip().decode()
    except Exception as _:
        # if file VERSION exists, use it
        if os.path.exists("VERSION"):
            with open("VERSION", "r") as f:
                tag = f.read().strip()
        else:
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
        tags=TAGS_METADATA,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": f"/static/{logo_name}",
        "altText": "Logo",
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]


@app.get("/docs", include_in_schema=False)
def overridden_swagger():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=TITLE,
        swagger_favicon_url=f"/static/{favicon_name}",
    )


@app.get("/redoc", include_in_schema=False)
def overridden_redoc():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=TITLE,
        redoc_favicon_url=f"/static/{favicon_name}",
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root():
    return API_LANDING_HTML.replace("[TITLE]", TITLE).replace("[LOGO_NAME]", logo_name)


def _load_runtime_routes():
    if getattr(app.state, "runtime_routes_loaded", False):
        return

    runtime_engine = engine.get()

    # Add agents to the API
    all_agents: list = []
    for module in runtime_engine.modules.values():
        for agent in module.agents:
            if agent is not None:
                all_agents.append(agent.New())
            else:
                logger.warning("Skipping agent (missing API key)")

    # Sort agents by name and add to router
    for runtime_agent in sorted(all_agents, key=lambda item: item.name):
        logger.debug(f"Adding agent to API: {runtime_agent.name}")
        runtime_agent.as_api(agents_router)

    # Include routers only once
    app.include_router(agents_router)
    app.include_router(pipelines_router)
    app.include_router(workflows_router)

    for module in runtime_engine.modules.values():
        module.api(app)

    app.state.runtime_routes_loaded = True


def get_app() -> FastAPI:
    _load_runtime_routes()
    return app


def api():
    import uvicorn

    reload_enabled = api_runtime_configuration.reload

    run_kwargs: dict = {
        "host": "0.0.0.0",
        "port": 9879,
        "reload": reload_enabled,
        "proxy_headers": True,
        "forwarded_allow_ips": "*",
        "log_level": "debug" if reload_enabled else "info",
    }

    if reload_enabled:
        run_kwargs["app"] = "naas_abi_core.apps.api.api:get_app"
        run_kwargs["factory"] = True
        run_kwargs["reload_dirs"] = ["src", "libs"]
    else:
        run_kwargs["app"] = get_app()

    uvicorn.run(**run_kwargs)


def test_init():
    logger.info("✅ API initialization completed successfully")
    print("API_INIT_TEST_PASSED")


if __name__ == "__main__":
    import sys

    if "--test-init" in sys.argv or os.environ.get("TEST_INIT") == "true":
        test_init()
    else:
        api()
