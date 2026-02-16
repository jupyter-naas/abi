"""
ABI Server Agent Sync - Automatically sync agents from external ABI servers.
"""

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import AgentConfigModel, InferenceServerModel
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class ABISyncResult(BaseModel):
    """Result of syncing agents from an ABI server."""

    server_id: str
    server_name: str
    agents_discovered: int
    agents_created: int
    agents_updated: int
    agents: list[str]


async def discover_abi_agents(endpoint: str, api_key: str | None = None) -> list[dict]:
    """
    Discover all available agents from an ABI server by fetching its OpenAPI spec.

    Args:
        endpoint: Base URL of the ABI server (e.g., https://abi-example.yourcompany.com)
        api_key: Optional API key/token for authentication

    Returns:
        List of agent info dicts with 'name', 'description', 'model_id'
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch OpenAPI spec
            openapi_url = f"{endpoint.rstrip('/')}/openapi.json"
            response = await client.get(openapi_url)
            response.raise_for_status()
            spec = response.json()

            # Extract all agent endpoints
            agents = []
            paths = spec.get("paths", {})

            for path, methods in paths.items():
                # Look for /agents/{name}/stream-completion endpoints
                if "/agents/" in path and "/stream-completion" in path:
                    # Extract agent name from path
                    parts = path.split("/")
                    if len(parts) >= 3:
                        agent_name = parts[2]  # /agents/{name}/stream-completion

                        # Get description from POST operation
                        post_op = methods.get("post", {})
                        description = post_op.get("description", "")

                        # Create model_id from agent name (replace spaces with underscores)
                        model_id = agent_name.replace(" ", "_")

                        agents.append(
                            {
                                "name": agent_name,
                                "description": description,
                                "model_id": model_id,
                                "endpoint_path": path,
                            }
                        )

            return agents

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to discover agents from ABI server: {str(e)}"
        ) from e


@router.post("/workspaces/{workspace_id}/abi-servers/{server_id}/sync")
async def sync_abi_agents(
    workspace_id: str,
    server_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> ABISyncResult:
    """
    Sync all agents from an ABI server into this workspace.
    Discovers agents from the server's OpenAPI spec and creates/updates them in the database.
    """
    # Check workspace access
    await require_workspace_access(current_user.id, workspace_id)

    # Get ABI server config from inference_servers table
    result = await db.execute(
        select(InferenceServerModel)
        .where(InferenceServerModel.id == server_id)
        .where(InferenceServerModel.workspace_id == workspace_id)
        .where(InferenceServerModel.type == "abi")
    )
    abi_server = result.scalar_one_or_none()

    if not abi_server:
        raise HTTPException(status_code=404, detail="ABI server not found")

    if not abi_server.enabled:
        raise HTTPException(status_code=400, detail="ABI server is disabled")

    # Discover agents from the ABI server
    discovered_agents = await discover_abi_agents(abi_server.endpoint, abi_server.api_key)

    agents_created = 0
    agents_updated = 0
    agent_names = []
    now = datetime.now(UTC).replace(tzinfo=None)

    for agent_info in discovered_agents:
        agent_id = f"agent-abi-{server_id}-{agent_info['model_id']}"
        agent_names.append(agent_info["name"])

        # Check if agent already exists
        existing = await db.execute(
            select(AgentConfigModel)
            .where(AgentConfigModel.id == agent_id)
            .where(AgentConfigModel.workspace_id == workspace_id)
        )
        existing_agent = existing.scalar_one_or_none()

        if existing_agent:
            # Update existing agent
            existing_agent.name = agent_info["name"]
            existing_agent.description = agent_info["description"]
            existing_agent.model_id = agent_info["model_id"]
            existing_agent.updated_at = now
            agents_updated += 1
        else:
            # Create new agent
            new_agent = AgentConfigModel(
                id=agent_id,
                workspace_id=workspace_id,
                name=agent_info["name"],
                description=agent_info["description"],
                provider="abi",
                model_id=agent_info["model_id"],
                system_prompt=f"You are {agent_info['name']}. {agent_info['description']}",
                logo_url=None,  # Could be extracted from spec if available
                enabled=False,  # Disabled by default - user must enable manually
                created_at=now,
                updated_at=now,
            )
            db.add(new_agent)
            agents_created += 1

    await db.commit()

    return ABISyncResult(
        server_id=server_id,
        server_name=abi_server.name,
        agents_discovered=len(discovered_agents),
        agents_created=agents_created,
        agents_updated=agents_updated,
        agents=agent_names,
    )


@router.get("/workspaces/{workspace_id}/abi-servers/{server_id}/discover")
async def discover_abi_server_agents(
    workspace_id: str,
    server_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Discover available agents from an ABI server without syncing them.
    Useful for preview before sync.
    """
    # Check workspace access
    await require_workspace_access(current_user.id, workspace_id)

    # Get ABI server config from inference_servers table
    result = await db.execute(
        select(InferenceServerModel)
        .where(InferenceServerModel.id == server_id)
        .where(InferenceServerModel.workspace_id == workspace_id)
        .where(InferenceServerModel.type == "abi")
    )
    abi_server = result.scalar_one_or_none()

    if not abi_server:
        raise HTTPException(status_code=404, detail="ABI server not found")

    # Discover agents
    agents = await discover_abi_agents(abi_server.endpoint, abi_server.api_key)

    return agents
