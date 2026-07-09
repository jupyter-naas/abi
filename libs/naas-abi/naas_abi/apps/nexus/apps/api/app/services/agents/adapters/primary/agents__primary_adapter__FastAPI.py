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
from naas_abi_core.services.agent.Agent import Agent

router = APIRouter(dependencies=[Depends(get_current_user_required)])

# ---------------------------------------------------------------------------
# Process-level agent class registry cache
#
# Building this registry is expensive: it iterates every engine module and
# triggers dynamic Python imports for all ~160 agent classes.  The classes
# themselves never change at runtime, so we compute the mapping once and
# reuse it for every subsequent request.
# ---------------------------------------------------------------------------
_agent_class_registry: dict[str, type[Agent]] | None = None
_agent_class_registry_lock = threading.Lock()


def _get_agent_class_registry() -> dict[str, type[Agent]]:
    """Return (and lazily build) the process-level agent class registry.

    Thread-safe double-checked locking ensures the expensive discovery runs
    at most once even under concurrent first requests.  Agent classes are
    resolved in parallel via a thread pool to minimise startup latency.
    """
    global _agent_class_registry

    if _agent_class_registry is not None:
        return _agent_class_registry

    with _agent_class_registry_lock:
        if _agent_class_registry is not None:
            return _agent_class_registry

        from concurrent.futures import ThreadPoolExecutor, as_completed

        from naas_abi import ABIModule

        abi_module = ABIModule.get_instance()
        candidate_classes: list[type[Agent]] = list(abi_module.agents)

        for module in abi_module.engine.modules.values():
            for agent_cls in module.agents:
                if agent_cls is None:
                    continue
                candidate_classes.append(agent_cls)

        def _resolve(agent_cls: type[Agent]) -> tuple[str, type[Agent]] | None:
            name = _get_agent_class_name(agent_cls)
            if not name:
                logger.warning(
                    "Skipping agent %s because it has no resolvable name"
                    " (use class attribute 'name' or 'NAME')",
                    agent_cls,
                )
                return None
            class_name = f"{agent_cls.__module__}/{agent_cls.__name__}"
            return class_name, agent_cls

        registry: dict[str, type[Agent]] = {}
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(_resolve, c): c for c in candidate_classes}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    class_name, agent_cls = result
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


def _extract_agent_suggestions(agent_cls: type) -> list[dict] | None:
    suggestions = getattr(agent_cls, "suggestions", None)
    if not isinstance(suggestions, list):
        return None

    normalized: list[dict] = []
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        value = item.get("value")
        if not isinstance(label, str) or not isinstance(value, str):
            continue
        entry: dict = {"label": label, "value": value}
        if "description" in item:
            entry["description"] = item["description"]
        if "disabled" in item:
            entry["disabled"] = item["disabled"]
        if "cta" in item:
            entry["cta"] = item["cta"]
        normalized.append(entry)
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


def _module_name_from_module_path(module_path: str | None) -> str | None:
    if not module_path:
        return None
    # module_path is a Python module path, module "name" is the top-level package
    # (e.g. naas_abi_marketplace from naas_abi_marketplace.applications.openrouter)
    return module_path.split(".", 1)[0] or None


def _normalize_logo_path_for_module(logo_url: str, module_name: str) -> str:
    """
    Convert absolute/container paths like:
      /app/libs/.../naas_abi_marketplace/.../logo.png
    into module-relative paths like:
      naas_abi_marketplace/.../logo.png
    """
    if logo_url.startswith(f"{module_name}/"):
        return logo_url
    if logo_url.startswith(f"/{module_name}/"):
        return logo_url.lstrip("/")
    idx = logo_url.find(f"{module_name}/")
    if idx >= 0:
        return logo_url[idx:]
    return logo_url.lstrip("/")


def _public_modules_url(path: str) -> str:
    from naas_abi import ABIModule

    public_api_host = ABIModule.get_instance().configuration.global_config.public_api_host
    if not public_api_host.startswith("https://"):
        public_api_host = f"https://{public_api_host}"
    return f"{public_api_host}/modules/{path.lstrip('/')}"


def _default_chat_model_id() -> str | None:
    """Canonical id of the engine's default chat model, or None.

    This is the model ABI agents (and any agent without an explicitly assigned
    ``model_id``) fall back to at runtime. Tries the running engine's model
    registry first, then the process-wide accessor. Never raises."""
    # Preferred: the running ABIModule's engine services (same handle this
    # adapter already uses for the agent-class registry).
    try:
        from naas_abi import ABIModule

        services = ABIModule.get_instance().engine.services
        if services.model_registry_available():
            model_id = services.model_registry.default_chat_model_id
            if model_id:
                return model_id
    except Exception:
        pass

    # Fallback: the process-wide registry singleton.
    try:
        from naas_abi_core.engine.context import get_default_model_registry

        registry = get_default_model_registry()
        if registry is not None:
            return registry.default_chat_model_id
    except Exception:
        return None
    return None


def _catalog_model_id_for_provider(provider: str) -> str | None:
    """Best-effort default model canonical id for a provider from the catalog.

    Matches the agent's ``provider`` (a provider name like ``openai`` or a
    catalog directory id like ``chatgpt``) against the marketplace model
    catalog and returns the first matching model's canonical id. Returns None
    when nothing matches."""
    key = provider.strip().lower()
    if not key:
        return None
    try:
        from naas_abi.apps.nexus.apps.api.app.services.providers.model_catalog import (
            list_catalog_models,
        )

        for entry in list_catalog_models():
            if key in (entry.provider_id.lower(), (entry.provider or "").lower()):
                return entry.canonical_id
    except Exception:
        return None
    return None


def _class_declared_model_id(agent_cls: type | None) -> str | None:
    """Model id declared by the agent class via ``get_chat_model_id``.

    This is the authoritative model for class-backed (ABI) agents — it mirrors
    the ``chat_model`` each agent builds in its ``New`` factory. Optional: agent
    classes that don't declare it fall through to other resolution steps."""
    if agent_cls is None:
        return None
    getter = getattr(agent_cls, "get_chat_model_id", None)
    if not callable(getter):
        return None
    try:
        model_id = getter()
    except Exception:
        return None
    if isinstance(model_id, str) and model_id.strip():
        return model_id.strip()
    return None


def _resolve_agent_model_id(agent: AgentRecord, agent_cls: type | None = None) -> str | None:
    """Resolve the model an agent will effectively run with.

    Priority: the agent's explicitly assigned ``model_id`` → the model declared
    by its agent class (``get_chat_model_id``) → a model from the marketplace
    catalog matching the agent's provider → the engine's default chat model.
    Returns None only when none of these resolve."""
    explicit = (agent.model_id or "").strip()
    if explicit and explicit.lower() not in ("none", "null"):
        return explicit

    class_model = _class_declared_model_id(agent_cls)
    if class_model:
        return class_model

    provider = (agent.provider or "").strip().lower()
    # "abi" agents don't map to a marketplace provider; they use the engine
    # default chat model, so skip the catalog lookup for them.
    if provider and provider != "abi":
        catalog_model = _catalog_model_id_for_provider(provider)
        if catalog_model:
            return catalog_model

    return _default_chat_model_id()


def _enrich_agent(
    agent: AgentRecord,
    class_name_to_agent_class: dict[str, type[Agent]],
) -> AgentRecord:
    """Return a copy of ``agent`` enriched with class-derived presentation fields.

    Pure and read-only: resolves the agent's class from the in-memory registry to
    attach suggestions, logo, intents, a derived ``module_path`` and the resolved
    model id.  Performs no database writes — any missing ``module_path`` is only
    derived in-memory here; persistence of that backfill happens in
    :func:`_reconcile_workspace_agents`.
    """
    suggestions = None
    logo_url = None
    intents = None
    resolved_cls: type | None = None
    module_path = agent.module_path
    if agent.class_name:
        resolved_cls = class_name_to_agent_class.get(agent.class_name)
        if resolved_cls is not None and isinstance(resolved_cls, type):
            suggestions = _extract_agent_suggestions(resolved_cls)
            logo_url = getattr(resolved_cls, "logo_url", None)
            intents = _extract_agent_intents(resolved_cls)
            if not module_path:
                module_path = getattr(resolved_cls, "__module__", None)

    # If module_path is still missing but class_name is available, derive it from class_name.
    if not module_path and agent.class_name and "/" in agent.class_name:
        module_path = agent.class_name.split("/", 1)[0] or None

    # Normalize logo_url to be module-relative, then convert to public /modules URL.
    if isinstance(logo_url, str) and logo_url:
        module_name = _module_name_from_module_path(module_path)
        if (
            module_name
            and module_name in logo_url
            and not (logo_url.startswith("http://") or logo_url.startswith("https://"))
        ):
            normalized_path = _normalize_logo_path_for_module(logo_url, module_name)
            logo_url = _public_modules_url(normalized_path)

    return replace(
        agent,
        module_path=module_path,
        suggestions=suggestions,
        logo_url=logo_url,
        intents=intents,
        resolved_model_id=_resolve_agent_model_id(agent, resolved_cls),
    )


async def _reconcile_workspace_agents(
    agent_service: AgentService,
    current_user: User,
    workspace_id: str,
    agent_list: list[AgentRecord],
    class_name_to_agent_class: dict[str, type[Agent]],
) -> list[AgentRecord]:
    """Reconcile persisted agent records with the code class registry.

    Mutating counterpart to the read-only listing:

    * **Prune** stale agents — records whose ``class_name`` is no longer present
      in the registry (their module/code was removed).  Agents without a
      ``class_name`` (e.g. manually created ones) are left untouched.
    * **Create** records for newly discovered agent classes.
    * **Backfill** a missing ``module_path`` on existing records.

    Returns the reconciled agent list (deleted records removed, created ones
    appended, backfilled ones refreshed).
    """
    context = request_context(current_user)
    existing_agents_by_class_name = {
        agent.class_name: agent for agent in agent_list if agent.class_name
    }

    # Prune agents persisted from a class that no longer exists in the registry.
    stale_agents = [
        agent
        for agent in agent_list
        if agent.class_name and agent.class_name not in class_name_to_agent_class
    ]
    for agent in stale_agents:
        logger.debug("Removing stale agent (class no longer in registry): %s", agent.class_name)
        await agent_service.delete_agent(context=context, agent_id=agent.id)
        existing_agents_by_class_name.pop(agent.class_name, None)
    if stale_agents:
        stale_ids = {agent.id for agent in stale_agents}
        agent_list = [agent for agent in agent_list if agent.id not in stale_ids]

    # Persist any newly discovered agent classes to the database.
    for class_name, agent_cls in class_name_to_agent_class.items():
        if class_name in existing_agents_by_class_name:
            continue

        name = _get_agent_class_name(agent_cls)
        description = _get_agent_class_description(agent_cls)
        enabled = name == "Abi"

        logger.debug("Creating agent in nexus backend: %s", name)
        system_prompt = _get_agent_system_prompt(agent_cls)
        created_agent = await agent_service.create_agent(
            context=context,
            data=AgentCreateInput(
                name=name,
                description=description or "",
                workspace_id=workspace_id,
                class_name=class_name,
                module_path=getattr(agent_cls, "__module__", None),
                provider="abi",
                enabled=enabled,
                system_prompt=system_prompt,
            ),
        )
        agent_list.append(created_agent)
        existing_agents_by_class_name[class_name] = created_agent

    # Backfill module_path (persist) when missing on existing DB records.
    reconciled: list[AgentRecord] = []
    for agent in agent_list:
        if not agent.module_path and agent.class_name:
            resolved_cls = class_name_to_agent_class.get(agent.class_name)
            module_path = getattr(resolved_cls, "__module__", None) if resolved_cls else None
            if module_path:
                updated = await agent_service.update_agent(
                    context=context,
                    agent_id=agent.id,
                    updates=AgentUpdateInput(module_path=module_path),
                )
                if updated is not None:
                    reconciled.append(updated)
                    continue
        reconciled.append(agent)
    return reconciled


@router.get("/")
async def list_agents(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> list[AgentRecord]:
    """Read-only listing of a workspace's persisted agents, enriched for display.

    Does not create, delete or otherwise mutate agent records; call
    ``POST /sync`` to reconcile the database with the code class registry.
    """
    if not workspace_id:
        return []

    await require_workspace_access(current_user.id, workspace_id)

    # Retrieve agent records from the database (fast)
    agent_list = await agent_service.list_workspace_agents(
        context=request_context(current_user),
        workspace_id=workspace_id,
    )

    # Retrieve the cached class registry — expensive only on the very first call
    # (triggers dynamic Python imports for all agent modules).  Subsequent calls
    # return instantly from the process-level cache.
    class_name_to_agent_class = _get_agent_class_registry()

    return [_enrich_agent(agent, class_name_to_agent_class) for agent in agent_list]


@router.post("/sync")
async def sync_agents(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> list[AgentRecord]:
    """Reconcile a workspace's persisted agents with the code class registry.

    Creates records for newly discovered agent classes, deletes stale ones whose
    class no longer exists in the registry, and backfills missing metadata — then
    returns the reconciled, enriched list.
    """
    if not workspace_id:
        return []

    await require_workspace_access(current_user.id, workspace_id)

    agent_list = await agent_service.list_workspace_agents(
        context=request_context(current_user),
        workspace_id=workspace_id,
    )

    class_name_to_agent_class = _get_agent_class_registry()

    agent_list = await _reconcile_workspace_agents(
        agent_service=agent_service,
        current_user=current_user,
        workspace_id=workspace_id,
        agent_list=agent_list,
        class_name_to_agent_class=class_name_to_agent_class,
    )

    return [_enrich_agent(agent, class_name_to_agent_class) for agent in agent_list]


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
            is_default=updates.is_default,
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
