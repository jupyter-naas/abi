"""
Agents API endpoints - Agent management and lifecycle.
"""

import logging

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
    from langchain_core.language_models.chat_models import BaseChatModel
    from naas_abi import ABIModule
    from naas_abi_core.models.Model import ChatModel
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

    for agent_cls in agents:
        agent_instance = agent_cls.New()
        class_name = f"{agent_cls.__module__}/{agent_cls.__name__}"
        existing_agent = existing_agents_by_name.get(agent_instance.name)
        if existing_agent and not existing_agent.class_name:
            try:
                await agent_service.update_agent(
                    existing_agent.id,
                    AgentUpdateInput(class_name=class_name),
                )
                for listed_agent in agent_list:
                    if listed_agent.id == existing_agent.id:
                        listed_agent.class_name = class_name
                        break
            except Exception as e:
                logger.warning(f"Failed to backfill class_name for agent {existing_agent.id}: {e}")
        if not existing_agent:
            logger.debug(f"Creating agent: {agent_instance.name}")
            try:
                name = agent_instance.name
                description = agent_instance.description
                system_prompt = agent_instance.configuration.system_prompt
                model_id = "unknown"
                # context_window = 4096
                # temperature = 0.7
                enabled = False
                if isinstance(agent_instance.chat_model, ChatModel):
                    if hasattr(agent_instance.chat_model, "model_id"):
                        model_id = agent_instance.chat_model.model_id
                    # if hasattr(agent_instance.chat_model, "context_window"):
                    #     context_window = agent_instance.chat_model.context_window
                    # if hasattr(agent_instance.chat_model, "model") and hasattr(
                    #     agent_instance.chat_model.model, "temperature"
                    # ):
                    #     temperature = agent_instance.chat_model.model.temperature
                elif isinstance(agent_instance.chat_model, BaseChatModel):
                    if hasattr(agent_instance.chat_model, "model") and isinstance(
                        agent_instance.chat_model.model, str
                    ):
                        model_id = agent_instance.chat_model.model
                    elif hasattr(agent_instance.chat_model, "model_name") and isinstance(
                        agent_instance.chat_model.model_name, str
                    ):
                        model_id = agent_instance.chat_model.model_name
                    # if hasattr(agent_instance.chat_model, "temperature") and isinstance(
                    #     agent_instance.chat_model.temperature, float
                    # ):
                    #     temperature = agent_instance.chat_model.temperature

                if agent_instance.name == "Abi":
                    enabled = True
                # Create agent in database
                agent_create = AgentCreateInput(
                    name=name,
                    description=description,
                    workspace_id=workspace_id,
                    class_name=class_name,
                    system_prompt=str(system_prompt),
                    model_id=model_id,
                    provider="abi",
                    enabled=enabled,
                )
                created_agent = await agent_service.create_agent(agent_create)
                agent_list.append(created_agent)
                existing_agents_by_name[name] = created_agent
            except Exception as e:
                logger.error(f"Error creating agent {agent_create}: {e}")
                continue

    return agent_list


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
