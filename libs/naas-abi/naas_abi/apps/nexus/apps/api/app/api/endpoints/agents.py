"""
Agents API endpoints - Agent management and lifecycle.
"""

import ast
import importlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User, get_current_user_required, require_workspace_access)
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import AgentConfigModel
from naas_abi.apps.nexus.apps.api.app.services.model_registry import (
    ModelInfo, get_all_models, get_logo_for_provider)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(get_current_user_required)])


class AgentCapability(BaseModel):
    """Agent capability definition."""

    name: str
    description: str
    enabled: bool = True


class AgentConfig(BaseModel):
    """Agent configuration."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    agent_type: Literal["aia", "bob", "system", "custom"]
    description: str | None = None
    system_prompt: str | None = None
    capabilities: list[AgentCapability] = []
    model: str = "gpt-4"
    provider: str | None = None  # Provider name (xai, openai, anthropic, etc.)
    logo_url: str | None = None  # URL to agent/provider logo
    enabled: bool = False  # Whether agent is available for chat
    temperature: float = 0.7
    max_tokens: int = 4096
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentStatus(BaseModel):
    """Agent runtime status."""

    agent_id: str
    status: Literal["active", "idle", "error", "offline"]
    last_activity: datetime | None = None
    active_conversations: int = 0
    error_message: str | None = None


class ToolExecution(BaseModel):
    """Tool execution request."""

    agent_id: str = Field(..., min_length=1, max_length=100)
    tool_name: str = Field(..., min_length=1, max_length=200)
    parameters: dict = Field(default={})
    context: dict = Field(default={})


class ToolResult(BaseModel):
    """Tool execution result."""

    success: bool
    result: dict | None = None
    error: str | None = None
    execution_time_ms: int


def _slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return value or "agent"


def _discover_loaded_abi_agents() -> list[AgentConfig]:
    """Discover agent metadata from loaded ABI modules without instantiating agents."""
    now = datetime.now(timezone.utc)
    discovered: list[AgentConfig] = []

    try:
        from naas_abi import ABIModule
        abi_module = ABIModule.get_instance()
    except Exception as exc:
        logger.debug(f"ABI module discovery unavailable: {exc}")
        return discovered

    modules = getattr(getattr(abi_module, "engine", None), "modules", {}) or {}
    for module in modules.values():
        for agent_cls in getattr(module, "agents", []) or []:
            if agent_cls is None:
                continue
            try:
                agent_mod = importlib.import_module(agent_cls.__module__)

                # Preferred metadata lives on the agent module.
                name = getattr(agent_mod, "NAME", None) or getattr(agent_cls, "NAME", None) or agent_cls.__name__
                description = (
                    getattr(agent_mod, "DESCRIPTION", None)
                    or getattr(agent_cls, "DESCRIPTION", None)
                    or f"Agent discovered from {module.__class__.__module__}"
                )
                logo_url = getattr(agent_mod, "AVATAR_URL", None) or getattr(agent_cls, "AVATAR_URL", None)

                discovered.append(
                    AgentConfig(
                        # Use class name as stable technical ID for wiring.
                        id=agent_cls.__name__,
                        name=name,
                        agent_type="custom",
                        description=description,
                        system_prompt=None,
                        model=name,
                        provider="abi",
                        logo_url=logo_url,
                        enabled=True,
                        temperature=0.7,
                        max_tokens=4096,
                        created_at=now,
                        updated_at=now,
                    )
                )
            except Exception as exc:
                logger.debug(f"Skipping agent metadata discovery for {agent_cls}: {exc}")
                continue

    return discovered


def _extract_string_constant(module_ast: ast.Module, constant_name: str) -> str | None:
    for node in module_ast.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == constant_name:
                    value = node.value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        return value.value
        if isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == constant_name:
                value = node.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    return value.value
    return None


def _extract_agent_class_name(module_ast: ast.Module) -> str | None:
    for node in module_ast.body:
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id in {"Agent", "IntentAgent"}:
                    return node.name
                if isinstance(base, ast.Attribute) and base.attr in {"Agent", "IntentAgent"}:
                    return node.name
    return None


def _discover_agents_from_naas_abi_directory() -> list[AgentConfig]:
    """Discover agents from `naas_abi/agents` via static file parsing only."""
    discovered: list[AgentConfig] = []
    now = datetime.now(timezone.utc)

    try:
        import naas_abi
        agents_dir = Path(naas_abi.__file__).resolve().parent / "agents"
    except Exception as exc:
        logger.debug(f"Could not resolve naas_abi agents directory: {exc}")
        return discovered

    if not agents_dir.exists():
        return discovered

    for file_path in agents_dir.glob("*.py"):
        if file_path.name.endswith("_test.py"):
            continue
        try:
            source = file_path.read_text(encoding="utf-8")
            module_ast = ast.parse(source, filename=str(file_path))

            name = _extract_string_constant(module_ast, "NAME")
            description = _extract_string_constant(module_ast, "DESCRIPTION")
            avatar_url = _extract_string_constant(module_ast, "AVATAR_URL")
            class_name = _extract_agent_class_name(module_ast)

            agent_name = name or class_name or file_path.stem
            agent_description = description or f"Agent discovered from {file_path.name}"

            discovered.append(
                AgentConfig(
                    # Use class name as stable technical ID for wiring when available.
                    id=class_name or file_path.stem,
                    name=agent_name,
                    agent_type="custom",
                    description=agent_description,
                    system_prompt=None,
                    model=agent_name,
                    provider="abi",
                    logo_url=avatar_url,
                    enabled=True,
                    temperature=0.7,
                    max_tokens=4096,
                    created_at=now,
                    updated_at=now,
                )
            )
        except Exception as exc:
            logger.debug(f"Failed to parse agent file {file_path}: {exc}")
            continue

    return discovered


# Default agents
default_agents: dict[str, AgentConfig] = {
    "aia": AgentConfig(
        id="aia",
        name="AIA",
        agent_type="aia",
        description="Personal AI Agent - Your personal assistant with access to your knowledge",
        capabilities=[
            AgentCapability(name="conversation", description="Natural language conversation"),
            AgentCapability(name="search", description="Search across your knowledge"),
            AgentCapability(name="ontology_read", description="Read ontology definitions"),
            AgentCapability(name="graph_read", description="Query knowledge graph"),
        ],
    ),
    "bob": AgentConfig(
        id="bob",
        name="BOB",
        agent_type="bob",
        description="Business Operations Bot - Specialized in business analysis and operations",
        capabilities=[
            AgentCapability(name="conversation", description="Natural language conversation"),
            AgentCapability(name="business_analysis", description="Analyze business data"),
            AgentCapability(name="reporting", description="Generate business reports"),
            AgentCapability(name="workflow", description="Execute business workflows"),
        ],
    ),
    "system": AgentConfig(
        id="system",
        name="System Agent",
        agent_type="system",
        description="NEXUS System Agent - Platform operations and administration",
        capabilities=[
            AgentCapability(name="platform_ops", description="Platform operations"),
            AgentCapability(name="data_management", description="Data import/export"),
            AgentCapability(name="ontology_write", description="Modify ontology"),
            AgentCapability(name="graph_write", description="Modify knowledge graph"),
        ],
    ),
}


@router.get("/")
async def list_agents(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[AgentConfig]:
    """List all agents. If workspace_id provided, returns workspace agents."""
    if not workspace_id:
        return []  # No workspace = no agents
    
    await require_workspace_access(current_user.id, workspace_id)
    
    result = await db.execute(
        select(AgentConfigModel).where(AgentConfigModel.workspace_id == workspace_id)
    )
    agents = result.scalars().all()
    
    # Return agents from database
    agent_list = []
    for agent in agents:
        agent_list.append(AgentConfig(
            id=agent.id,
            name=agent.name,
            agent_type="custom",
            description=agent.description or "",
            system_prompt=agent.system_prompt or "",
            model=agent.model_id or "unknown",
            provider=agent.provider,  # Include provider name
            logo_url=agent.logo_url,  # Include logo URL
            enabled=agent.enabled if hasattr(agent, 'enabled') else False,  # Include enabled status
            temperature=0.7,  # Default value
            max_tokens=4096,  # Default value
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        ))

    # Add discovered ABI agents (no instantiation), unless already present by name.
    discovered_agents = (
        _discover_loaded_abi_agents() + _discover_agents_from_naas_abi_directory()
    )
    existing_names = {a.name.strip().lower() for a in agent_list}
    for discovered in discovered_agents:
        if discovered.name.strip().lower() not in existing_names:
            agent_list.append(discovered)
            existing_names.add(discovered.name.strip().lower())

    return agent_list


class AgentCreate(BaseModel):
    """Create a new agent."""
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    system_prompt: str | None = None
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 4096
    workspace_id: str


@router.post("/")
async def create_agent(
    agent: AgentCreate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> AgentConfig:
    """Create a custom agent."""
    await require_workspace_access(current_user.id, agent.workspace_id)
    
    agent_model = AgentConfigModel(
        id=str(uuid4()),
        workspace_id=agent.workspace_id,
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        model_id=agent.model,
        enabled=False,  # New agents disabled by default
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
    )
    
    db.add(agent_model)
    await db.commit()
    await db.refresh(agent_model)
    
    return AgentConfig(
        id=agent_model.id,
        name=agent_model.name,
        agent_type="custom",
        description=agent_model.description,
        system_prompt=agent_model.system_prompt,
        model=agent_model.model_id or "unknown",
        provider=agent_model.provider,
        logo_url=agent_model.logo_url,
        enabled=agent_model.enabled if hasattr(agent_model, 'enabled') else False,
        temperature=agent_model.temperature or 0.7,
        max_tokens=agent_model.max_tokens or 4096,
        created_at=agent_model.created_at,
        updated_at=agent_model.updated_at,
    )


class AgentUpdate(BaseModel):
    """Update an agent."""
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    enabled: bool | None = None
    temperature: float | None = None
    max_tokens: int | None = None


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str,
    updates: AgentUpdate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> AgentConfig:
    """Update an agent."""
    result = await db.execute(
        select(AgentConfigModel).where(AgentConfigModel.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    await require_workspace_access(current_user.id, agent.workspace_id)
    
    # Update fields
    if updates.name is not None:
        agent.name = updates.name
    if updates.description is not None:
        agent.description = updates.description
    if updates.system_prompt is not None:
        agent.system_prompt = updates.system_prompt
    if updates.model is not None:
        agent.model_id = updates.model
    if updates.enabled is not None:
        agent.enabled = updates.enabled
    # Note: temperature and max_tokens are not stored in DB
    
    agent.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await db.refresh(agent)
    
    return AgentConfig(
        id=agent.id,
        name=agent.name,
        agent_type="custom",
        description=agent.description or "",
        system_prompt=agent.system_prompt or "",
        model=agent.model_id or "unknown",
        provider=agent.provider,
        logo_url=agent.logo_url,
        enabled=agent.enabled if hasattr(agent, 'enabled') else False,
        temperature=0.7,  # Default value - not stored in DB
        max_tokens=4096,  # Default value - not stored in DB
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete an agent."""
    result = await db.execute(
        select(AgentConfigModel).where(AgentConfigModel.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    await require_workspace_access(current_user.id, agent.workspace_id)
    
    await db.delete(agent)
    await db.commit()
    
    return {"status": "deleted"}


class AgentSyncResult(BaseModel):
    """Result of agent sync operation."""
    created: int
    skipped: int
    total_models: int
    agent_ids: list[str]


@router.post("/sync")
async def sync_agents_from_models(
    workspace_id: str,
    server_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> AgentSyncResult:
    """
    Sync agents from model registry or from an ABI server.
    
    If server_id is provided, syncs agents from that ABI server.
    Otherwise, syncs from the centralized model registry.
    
    Creates one agent per model/agent found. Skips if already exists.
    """
    await require_workspace_access(current_user.id, workspace_id)
    
    created_count = 0
    skipped_count = 0
    agent_ids = []
    
    # Get existing agents for this workspace
    result = await db.execute(
        select(AgentConfigModel).where(AgentConfigModel.workspace_id == workspace_id)
    )
    existing_agents = result.scalars().all()
    existing_model_ids = {agent.model_id for agent in existing_agents if agent.model_id}
    existing_names = {agent.name.lower() for agent in existing_agents}
    
    if server_id:
        # Sync from ABI server
        import httpx
        from naas_abi.apps.nexus.apps.api.app.models import \
            InferenceServerModel

        # Get server
        server_result = await db.execute(
            select(InferenceServerModel).where(
                (InferenceServerModel.id == server_id) &
                (InferenceServerModel.workspace_id == workspace_id)
            )
        )
        server = server_result.scalar_one_or_none()
        
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        
        if server.type != 'abi':
            raise HTTPException(status_code=400, detail="Only ABI servers support agent discovery")
        
        # Try to discover agents from the ABI server
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {}
                if server.api_key:
                    headers['Authorization'] = f'Bearer {server.api_key}'
                
                # Try common ABI agent discovery endpoints
                agents_endpoint = f"{server.endpoint}/agents"
                response = await client.get(agents_endpoint, headers=headers)
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to fetch agents from server: {response.status_code}"
                    )
                
                abi_agents = response.json()
                
                for abi_agent in abi_agents:
                    agent_name = abi_agent.get('name', abi_agent.get('id', 'Unknown Agent'))
                    
                    # Skip if agent with this name already exists
                    if agent_name.lower() in existing_names:
                        skipped_count += 1
                        continue
                    
                    description = abi_agent.get('description', f'Agent from {server.name}')
                    system_prompt = abi_agent.get('system_prompt', abi_agent.get('prompt', """You are a helpful AI assistant."""))
                    
                    # Create agent
                    agent_model = AgentConfigModel(
                        id=str(uuid4()),
                        workspace_id=workspace_id,
                        name=agent_name,
                        description=description,
                        system_prompt=system_prompt,
                        model_id=abi_agent.get('id'),
                        provider='abi',
                        logo_url=abi_agent.get('logo_url'),
                        enabled=False,  # Disabled by default
                    )
                    
                    db.add(agent_model)
                    agent_ids.append(agent_model.id)
                    created_count += 1
                
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to connect to ABI server: {str(e)}"
            )
    else:
        # Sync from model registry (existing logic)
        all_models = get_all_models()
        
        for model_info in all_models:
            model_id = model_info["id"]
            
            # Skip if agent already exists for this model
            if model_id in existing_model_ids:
                skipped_count += 1
                continue
            
            # Create agent name based on model
            agent_name = model_info["name"]
            
            # Generate description with capabilities
            capabilities = []
            if model_info["supports_streaming"]:
                capabilities.append("streaming")
            if model_info["supports_vision"]:
                capabilities.append("vision")
            if model_info["supports_function_calling"]:
                capabilities.append("function calling")
            
            capability_text = ", ".join(capabilities) if capabilities else "standard chat"
            description = f"{model_info['name']} ({model_info['provider']}) - {capability_text}. Context: {model_info['context_window']:,} tokens"
            
            # Standard system prompt for all agents
            system_prompt = """You are a helpful AI assistant. Your role is to:
- Provide accurate, thoughtful responses
- Ask clarifying questions when needed
- Break down complex problems into steps
- Cite sources when appropriate
- Admit when you don't know something

Always be respectful, clear, and focused on helping the user achieve their goals."""
            
            # Create agent
            agent_model = AgentConfigModel(
                id=str(uuid4()),
                workspace_id=workspace_id,
                name=agent_name,
                description=description,
                system_prompt=system_prompt,
                model_id=model_id,
                provider=model_info["provider"],
                logo_url=get_logo_for_provider(model_info["provider"]),
                enabled=False,  # Disabled by default
            )
            
            db.add(agent_model)
            agent_ids.append(agent_model.id)
            created_count += 1
    
    if created_count > 0:
        await db.commit()
        logger.info(f"Synced {created_count} agents for workspace {workspace_id}")
    
    return AgentSyncResult(
        created=created_count,
        skipped=skipped_count,
        total_models=len(existing_model_ids) + created_count if not server_id else created_count + skipped_count,
        agent_ids=agent_ids,
    )


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> AgentConfig:
    """Get agent configuration by ID."""
    # Check default agents first
    if agent_id in default_agents:
        return default_agents[agent_id]
    
    # Check database for custom agents
    result = await db.execute(
        select(AgentConfigModel).where(AgentConfigModel.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Verify user has access to the workspace
    await require_workspace_access(current_user.id, agent.workspace_id)
    
    return AgentConfig(
        id=agent.id,
        name=agent.name,
        agent_type="custom",
        description=agent.description or "",
        system_prompt=agent.system_prompt or "",
        model=agent.model_id or "unknown",
        provider=agent.provider,
        logo_url=agent.logo_url,
        temperature=0.7,
        max_tokens=4096,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str) -> AgentStatus:
    """Get agent runtime status."""
    if agent_id not in default_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # TODO: Get actual status from ABI engine
    return AgentStatus(
        agent_id=agent_id,
        status="active",
        last_activity=datetime.now(timezone.utc),
        active_conversations=0,
    )


@router.get("/{agent_id}/capabilities")
async def get_agent_capabilities(agent_id: str) -> list[AgentCapability]:
    """Get agent capabilities."""
    if agent_id not in default_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    return default_agents[agent_id].capabilities


@router.post("/{agent_id}/tools/execute")
async def execute_tool(agent_id: str, execution: ToolExecution) -> ToolResult:
    """
    Execute a tool on behalf of an agent.
    
    This endpoint allows triggering specific tools/workflows
    that an agent can execute.
    """
    if agent_id not in default_agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # TODO: Implement actual tool execution via ABI
    return ToolResult(
        success=True,
        result={"message": f"Tool '{execution.tool_name}' execution not yet implemented"},
        execution_time_ms=0,
    )
