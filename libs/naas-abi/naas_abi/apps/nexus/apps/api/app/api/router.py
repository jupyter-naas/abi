"""
Main API router that aggregates all endpoint routers.
"""

from fastapi import APIRouter
from naas_abi.apps.nexus.apps.api.app.api.endpoints import (
    abi,
    graph,
    ontology,
    organizations,
    search,
    secrets,
    tenant,
    transcribe,
    view,
    websocket,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.handlers import router as agents_router
from naas_abi.apps.nexus.apps.api.app.services.apps.handlers import router as apps_router
from naas_abi.apps.nexus.apps.api.app.services.auth.handlers import router as auth_router
from naas_abi.apps.nexus.apps.api.app.services.chat.handlers import router as chat_router
from naas_abi.apps.nexus.apps.api.app.services.code.handlers import (
    filesystem_router as code_filesystem_router,
)
from naas_abi.apps.nexus.apps.api.app.services.code.handlers import (
    logs_router as code_logs_router,
)
from naas_abi.apps.nexus.apps.api.app.services.code.handlers import (
    opencode_router as code_opencode_router,
)
from naas_abi.apps.nexus.apps.api.app.services.code.handlers import (
    sync_router as code_sync_router,
)
from naas_abi.apps.nexus.apps.api.app.services.code.handlers import (
    terminal_router as code_terminal_router,
)
from naas_abi.apps.nexus.apps.api.app.services.files.handlers import router as files_router
from naas_abi.apps.nexus.apps.api.app.services.modules.handlers import router as modules_router
from naas_abi.apps.nexus.apps.api.app.services.providers.handlers import router as providers_router
from naas_abi.apps.nexus.apps.api.app.services.workspaces.handlers import (
    router as workspaces_router,
)

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(
    organizations.public_router, prefix="/organizations", tags=["organizations-public"]
)
api_router.include_router(workspaces_router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(ontology.router, prefix="/ontology", tags=["ontology"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(view.router, prefix="/view", tags=["view"])
api_router.include_router(agents_router, prefix="/agents", tags=["agents"])
api_router.include_router(modules_router, prefix="/modules", tags=["modules"])
api_router.include_router(apps_router, prefix="/apps", tags=["apps"])
api_router.include_router(files_router, prefix="/files", tags=["files"])
api_router.include_router(code_sync_router, prefix="/code", tags=["code"])
api_router.include_router(code_filesystem_router, prefix="/filesystem", tags=["code"])
api_router.include_router(code_opencode_router, prefix="/opencode", tags=["code"])
api_router.include_router(code_terminal_router, prefix="/terminal", tags=["code"])
api_router.include_router(code_logs_router, prefix="/logs", tags=["code"])
api_router.include_router(secrets.router, prefix="/secrets", tags=["secrets"])
api_router.include_router(providers_router, prefix="/providers", tags=["providers"])
api_router.include_router(websocket.router, prefix="/websocket", tags=["websocket"])
api_router.include_router(abi.router, prefix="/abi", tags=["abi"])
api_router.include_router(tenant.router, prefix="/tenant", tags=["tenant"])
api_router.include_router(transcribe.router, prefix="/transcribe", tags=["transcribe"])
