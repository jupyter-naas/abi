"""
Agents API endpoints - Agent management and lifecycle.
"""

import logging
from dataclasses import replace

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.agents import (
    AgentCreateInput,
    AgentFactory,
    AgentRecord,
    AgentService,
    AgentUpdateInput,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(get_current_user_required)])


def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    return AgentFactory.ServicePostgres(db)


def _extract_agent_suggestions(agent_cls: type) -> list[dict[str, str]] | None:
    """Return normalized class suggestions when available."""
    suggestions = getattr(agent_cls, "suggestions", None)
    if not isinstance(suggestions, list):
        return None

    normalized: list[dict[str, str]] = []
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        value = item.get("value")
        if isinstance(label, str) and isinstance(value, str):
            normalized.append({"label": label, "value": value})
    return normalized


@router.get("/")
async def list_agents(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> list[AgentRecord]:
    """List all agents. If workspace_id provided, returns workspace agents."""
    if not workspace_id:
        return []  # No workspace = no agents

    await require_workspace_access(current_user.id, workspace_id)

    agent_list = await agent_service.list_workspace_agents(workspace_id)
    existing_agents_by_name = {agent.name: agent for agent in agent_list}

    # Add agents from engine modules to the API
    from naas_abi import ABIModule
    from naas_abi_core.services.agent.Agent import Agent

    abi_module = ABIModule.get_instance()
    module_agents = list(abi_module.agents)
    agents: list[type[Agent]] = []
    agents.extend(module_agents)

    for module in abi_module.engine.modules.values():
        for agent_cls in module.agents:
            if agent_cls is None:
                continue
            agents.append(agent_cls)

    class_name_to_agent_class: dict[str, type[Agent]] = {}

    for agent_cls in agents:
        if not hasattr(agent_cls, "name"):
            logger.warning(f"Skipping agent {agent_cls} because it has no name or description")
            continue

        name = agent_cls.name
        description = agent_cls.description
        class_name = f"{agent_cls.__module__}/{agent_cls.__name__}"
        class_name_to_agent_class[class_name] = agent_cls
        existing_agent = existing_agents_by_name.get(str(name))
        enabled = False
        if name == "Abi":
            enabled = True

        if not existing_agent:
            logger.debug(f"Creating agent: {name}")

            # Create agent in database
            agent_create = AgentCreateInput(
                name=str(name),
                description=str(description),
                workspace_id=workspace_id,
                class_name=class_name,
                provider="abi",
                enabled=enabled,
            )
            created_agent = await agent_service.create_agent(agent_create)

            # Add created agent to list
            agent_list.append(created_agent)
            existing_agents_by_name[str(name)] = created_agent

    enriched_agent_list: list[AgentRecord] = []
    for agent in agent_list:
        suggestions = None
        if agent.class_name:
            agent_cls = class_name_to_agent_class.get(agent.class_name)
            if agent_cls is not None:
                suggestions = _extract_agent_suggestions(agent_cls)
        enriched_agent_list.append(replace(agent, suggestions=suggestions))

    return enriched_agent_list


@router.post("/")
async def create_agent(
    agent: AgentCreateInput,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    """Create a custom agent."""
    await require_workspace_access(current_user.id, agent.workspace_id)

    created_agent = await agent_service.create_agent(agent)

    logger.debug(f"Agent created: {created_agent}")
    return created_agent


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str,
    updates: AgentUpdateInput,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    """Update an agent."""
    existing_agent = await agent_service.get_agent(agent_id)
    if not existing_agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await require_workspace_access(current_user.id, existing_agent.workspace_id)

    updated_agent = await agent_service.update_agent(
        agent_id,
        AgentUpdateInput(
            name=updates.name,
            description=updates.description,
            system_prompt=updates.system_prompt,
            model_id=updates.model,
            enabled=updates.enabled,
        ),
    )
    if updated_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    return updated_agent


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> dict[str, str]:
    """Delete an agent."""
    existing_agent = await agent_service.get_agent(agent_id)
    if not existing_agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await require_workspace_access(current_user.id, existing_agent.workspace_id)
    await agent_service.delete_agent(agent_id)
    return {"status": "deleted"}


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    """Get agent configuration by ID."""
    agent = await agent_service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Verify user has access to the workspace
    await require_workspace_access(current_user.id, agent.workspace_id)

    return agent
