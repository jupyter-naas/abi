"""
Main API router that aggregates all endpoint routers.
"""

from fastapi import APIRouter

from app.api.endpoints import auth, chat, search, ontology, graph, agents, files, workspaces, secrets, websocket, providers, abi, abi_sync, organizations

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(organizations.public_router, prefix="/organizations", tags=["organizations-public"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(ontology.router, prefix="/ontology", tags=["ontology"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(secrets.router, prefix="/secrets", tags=["secrets"])
api_router.include_router(providers.router, prefix="/providers", tags=["providers"])
api_router.include_router(websocket.router, prefix="/websocket", tags=["websocket"])
api_router.include_router(abi.router, prefix="/abi", tags=["abi"])
api_router.include_router(abi_sync.router, prefix="/abi", tags=["abi-sync"])
