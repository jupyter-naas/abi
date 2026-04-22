"""Agents FastAPI primary adapter."""

from __future__ import annotations

import threading
from dataclasses import replace

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.services.agents import (
    AgentCreateInput,
    AgentRecord,
    AgentService,
    AgentUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
from naas_abi.apps.nexus.apps.api.app.services.registry import (
    ServiceRegistry,
    get_service_registry,
)
from naas_abi_core import logger

router = APIRouter(dependencies=[Depends(get_current_user_required)])

# ---------------------------------------------------------------------------
# Process-level agent class registry cache
#
# Building this registry is expensive: it iterates every engine module and
# triggers dynamic Python imports for all ~160 agent classes.  The classes
# themselves never change at runtime, so we compute the mapping once and
# reuse it for every subsequent request.
# ---------------------------------------------------------------------------
_agent_class_registry: dict[str, type[Agent]] | None = None  # noqa: F821
_agent_class_registry_lock = threading.Lock()


def _get_agent_class_registry() -> dict[str, type[Agent]]:  # noqa: F821
    """Return (and lazily build) the process-level agent class registry.

    Thread-safe double-checked locking ensures the expensive discovery runs
    at most once even under concurrent first requests.
    """
    global _agent_class_registry

    if _agent_class_registry is not None:
        return _agent_class_registry

    with _agent_class_registry_lock:
        if _agent_class_registry is not None:
            return _agent_class_registry

        from naas_abi import ABIModule
        from naas_abi_core.services.agent.Agent import Agent

        abi_module = ABIModule.get_instance()
        all_agent_classes: list[type[Agent]] = list(abi_module.agents)

        for module in abi_module.engine.modules.values():
            for agent_cls in module.agents:
                if agent_cls is None:
                    continue
                all_agent_classes.append(agent_cls)

        registry: dict[str, type[Agent]] = {}
        for agent_cls in all_agent_classes:
            name = _get_agent_class_name(agent_cls)
            if not name:
                logger.warning(
                    "Skipping agent %s because it has no resolvable name"
                    " (use class attribute 'name' or 'NAME')",
                    agent_cls,
                )
                continue
            class_name = f"{agent_cls.__module__}/{agent_cls.__name__}"
            registry[class_name] = agent_cls

        logger.info("Agent class registry built: %d agents indexed", len(registry))
        _agent_class_registry = registry
        return _agent_class_registry


class AgentsFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


def get_agent_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> AgentService:
    return registry.agents


def request_context(current_user: User) -> RequestContext:
    return RequestContext(
        token_data=TokenData(user_id=current_user.id, scopes={"*"}, is_authenticated=True)
    )


def _extract_agent_suggestions(agent_cls: type) -> list[dict[str, str]] | None:
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


def _get_agent_class_name(agent_cls: type) -> str | None:
    name = getattr(agent_cls, "name", None)
    if isinstance(name, str):
        return name
    if isinstance(name, property):
        name = getattr(agent_cls, "NAME", None)
    return name if isinstance(name, str) else None


def _get_agent_class_description(agent_cls: type) -> str | None:
    desc = getattr(agent_cls, "description", None)
    if isinstance(desc, str):
        return desc
    if isinstance(desc, property):
        desc = getattr(agent_cls, "DESCRIPTION", None)
    return desc if isinstance(desc, str) else None


def _get_agent_system_prompt(agent_cls: type) -> str | None:
    system_prompt = getattr(agent_cls, "system_prompt", None)
    if isinstance(system_prompt, str):
        return system_prompt
    from naas_abi_core.services.agent.Agent import AgentConfiguration

    config = AgentConfiguration()
    return config.get_system_prompt([])


def _extract_agent_intents(agent_cls: type) -> list[dict[str, str]] | None:
    raw = getattr(agent_cls, "intents", None)
    if not isinstance(raw, list) or not raw:
        return None

    output: list[dict[str, str]] = []
    for item in raw:
        if not hasattr(item, "intent_value") or not hasattr(item, "intent_type"):
            continue

        intent_payload: dict[str, str] = {
            "intent_value": getattr(item, "intent_value", ""),
            "intent_type": getattr(item.intent_type, "value", str(item.intent_type)),
            "intent_target": str(getattr(item, "intent_target", "")),
        }
        scope = getattr(item, "intent_scope", None)
        if scope is not None and hasattr(scope, "value"):
            intent_payload["intent_scope"] = scope.value
        else:
            intent_payload["intent_scope"] = str(scope) if scope is not None else ""

        output.append(intent_payload)

    return output if output else None


@router.get("/")
async def list_agents(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> list[AgentRecord]:
    if not workspace_id:
        return []

    await require_workspace_access(current_user.id, workspace_id)

    # Retrieve agent records from the database (fast)
    agent_list = await agent_service.list_workspace_agents(
        context=request_context(current_user),
        workspace_id=workspace_id,
    )
    existing_agents_by_class_name = {
        agent.class_name: agent for agent in agent_list if agent.class_name
    }

    # Retrieve the cached class registry — expensive only on the very first call
    # (triggers dynamic Python imports for all agent modules).  Subsequent calls
    # return instantly from the process-level cache.
    class_name_to_agent_class = _get_agent_class_registry()

    # Persist any newly discovered agent classes to the database
    for class_name, agent_cls in class_name_to_agent_class.items():
        if class_name in existing_agents_by_class_name:
            continue

        name = _get_agent_class_name(agent_cls)
        description = _get_agent_class_description(agent_cls)
        enabled = name == "Abi"

        logger.debug("Creating agent in nexus backend: %s", name)
        system_prompt = _get_agent_system_prompt(agent_cls)
        created_agent = await agent_service.create_agent(
            context=request_context(current_user),
            data=AgentCreateInput(
                name=name,
                description=description or "",
                workspace_id=workspace_id,
                class_name=class_name,
                provider="abi",
                enabled=enabled,
                system_prompt=system_prompt,
            ),
        )
        agent_list.append(created_agent)
        existing_agents_by_class_name[class_name] = created_agent

    # Enrich DB records with class-level metadata (suggestions, logo, intents)
    enriched_agent_list: list[AgentRecord] = []
    for agent in agent_list:
        suggestions = None
        logo_url = None
        intents = None
        if agent.class_name:
            resolved_cls = class_name_to_agent_class.get(agent.class_name)
            if resolved_cls is not None and isinstance(resolved_cls, type):
                suggestions = _extract_agent_suggestions(resolved_cls)
                logo_url = getattr(resolved_cls, "logo_url", None)
                intents = _extract_agent_intents(resolved_cls)
        enriched_agent_list.append(
            replace(agent, suggestions=suggestions, logo_url=logo_url, intents=intents)
        )

    return enriched_agent_list


@router.post("/")
async def create_agent(
    agent: AgentCreateInput,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    await require_workspace_access(current_user.id, agent.workspace_id)
    created_agent = await agent_service.create_agent(
        context=request_context(current_user),
        data=agent,
    )
    logger.debug("Agent created: %s", created_agent)
    return created_agent


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str,
    updates: AgentUpdateInput,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    existing_agent = await agent_service.get_agent(
        context=request_context(current_user),
        agent_id=agent_id,
    )
    if not existing_agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await require_workspace_access(current_user.id, existing_agent.workspace_id)

    updated_agent = await agent_service.update_agent(
        context=request_context(current_user),
        agent_id=agent_id,
        updates=AgentUpdateInput(
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
    existing_agent = await agent_service.get_agent(
        context=request_context(current_user),
        agent_id=agent_id,
    )
    if not existing_agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await require_workspace_access(current_user.id, existing_agent.workspace_id)
    await agent_service.delete_agent(
        context=request_context(current_user),
        agent_id=agent_id,
    )
    return {"status": "deleted"}


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    agent = await agent_service.get_agent(
        context=request_context(current_user),
        agent_id=agent_id,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await require_workspace_access(current_user.id, agent.workspace_id)
    return agent
