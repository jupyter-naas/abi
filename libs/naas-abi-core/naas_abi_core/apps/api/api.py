import sys
import time

_BOOT_T0 = time.monotonic()
print(
    f"[abi-boot] api module import started (pid={__import__('os').getpid()})",
    file=sys.stderr,
    flush=True,
)

import os
import subprocess
from importlib.resources import files
from typing import Annotated

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

print(
    f"[abi-boot] heavy imports starting (+{time.monotonic() - _BOOT_T0:.2f}s)",
    file=sys.stderr,
    flush=True,
)
from naas_abi_core import logger

print(
    f"[abi-boot] naas_abi_core imported (+{time.monotonic() - _BOOT_T0:.2f}s)",
    file=sys.stderr,
    flush=True,
)

# Docs
from naas_abi_core.apps.api.openapi_doc import API_LANDING_HTML
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    ApiConfiguration,
    EngineConfiguration,
)


def _load_api_runtime_configuration() -> ApiConfiguration:
    try:
        return EngineConfiguration.load_configuration().api
    except Exception as exc:  # noqa: BLE001
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

# Allow callers (e.g. `abi dev`) to inject additional origins at runtime so
# the config file does not need to know about dynamically-allocated dev ports.
# We mutate the shared Pydantic object — not just a local copy — so downstream
# consumers (Nexus CORSMiddleware, Socket.IO) which read
# `app.state.abi_cors_origins = engine.api_configuration.cors_origins`
# see the same expanded list.
_extra_origins_env = os.environ.get("ABI_CORS_EXTRA_ORIGINS", "")
for _extra in (o.strip() for o in _extra_origins_env.split(",")):
    if _extra and _extra not in api_runtime_configuration.cors_origins:
        api_runtime_configuration.cors_origins.append(_extra)

origins = list(api_runtime_configuration.cors_origins)
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
        scheme_name: str | None = None,
        auto_error: bool = True,
    ):
        flows = OAuthFlowsModel(password=OAuthFlowPassword(tokenUrl=tokenUrl))
        super().__init__(flows=flows, scheme_name=scheme_name, auto_error=auto_error)

    async def __call__(self, request: Request) -> str | None:
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
    from naas_abi_core.apps.api.abi_api_key_auth import is_abi_api_token_valid

    if not is_abi_api_token_valid(token):
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

    return {
        "access_token": os.environ.get("ABI_API_KEY", "abi"),
        "token_type": "bearer",
    }


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

# Create Workflows API Router
workflows_router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"],
    responses={401: {"description": "Unauthorized"}},
    dependencies=[Depends(is_token_valid)],  # Apply token verification
)

# Create Tools API Router. Only Expose tools that register routes are mounted.
# LangChain BaseTool instances stay agent-internal.
tools_router = APIRouter(
    prefix="/tools",
    tags=["Tools"],
    responses={401: {"description": "Unauthorized"}},
    dependencies=[Depends(is_token_valid)],
)


def get_git_tag():
    try:
        tag = subprocess.check_output(["git", "describe", "--tags"]).strip().decode()
    except Exception as _:  # noqa: BLE001
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
        # tags=TAGS_METADATA,
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

    from naas_abi_core.utils.process_api import mount_module_processes

    mount_module_processes(
        runtime_engine.modules.values(),
        workflows_router=workflows_router,
        pipelines_router=pipelines_router,
        tools_router=tools_router,
    )

    # Include routers only once. Process routers stay out of OpenAPI when
    # empty so Workflows / Pipelines / Tools tags are not advertised as live.
    app.include_router(agents_router)
    if pipelines_router.routes:
        app.include_router(pipelines_router)
    if workflows_router.routes:
        app.include_router(workflows_router)
    if tools_router.routes:
        app.include_router(tools_router)

    for module in runtime_engine.modules.values():
        public_dir = os.path.join(module.module_root_path, "assets", "public")
        if os.path.isdir(public_dir):
            module_url_path = module.__class__.__module__.replace(".", "/")
            mount_path = f"/modules/{module_url_path}/assets/public"
            logger.debug(f"Mounting module public assets: {mount_path} -> {public_dir}")
            app.mount(
                mount_path,
                StaticFiles(directory=public_dir),
                name=f"module-{module_url_path.replace('/', '-')}-public",
            )

    for module in runtime_engine.modules.values():
        module.api(app)

    # Protect /app-html/ with ABI_API_KEY (same channels as /agents). Added last
    # so it runs outermost — before per-app object-storage middlewares.
    from naas_abi_core.apps.api.abi_api_key_auth import AppHtmlAbiKeyMiddleware

    app.add_middleware(AppHtmlAbiKeyMiddleware)

    # Kick off background warmup of every IntentMapper's vector index. We
    # deferred this work out of agent __init__ to keep boot fast; doing it
    # now in the background means the index is normally ready before the
    # first chat request arrives. If a request does race it, the request's
    # `_ensure_index` call will block briefly on the same lock and reuse
    # whatever the warmup has already built.
    try:
        from naas_abi_core.services.agent.beta.IntentMapper import IntentMapper

        IntentMapper.warm_all_in_background()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Could not start intent-index warmup thread: {exc}")

    app.state.runtime_routes_loaded = True


def get_app() -> FastAPI:
    _load_runtime_routes()
    return app


def api():
    print(
        f"[abi-boot] api() entered, starting uvicorn (+{time.monotonic() - _BOOT_T0:.2f}s)",
        file=sys.stderr,
        flush=True,
    )
    import uvicorn

    reload_enabled = api_runtime_configuration.reload
    host = os.environ.get("ABI_HOST", api_runtime_configuration.host)
    port = int(os.environ.get("ABI_PORT", api_runtime_configuration.port))

    run_kwargs: dict = {
        "host": host,  # nosec B104 - default binds all interfaces per configuration
        "port": port,
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
