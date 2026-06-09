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

# ---------------------------------------------------------------------------
# Process-level agent INSTANCE cache
#
# Instantiating an agent (via ``cls.New()``) builds its tool chain and any
# sub-agents.  This is expensive enough that we only do it on demand and we
# cache the result per agent class for the lifetime of the process.  Internal
# tools (``transfer_to_*`` handoff tools, ``request_help``) are filtered out
# of the exposed tool list.
# ---------------------------------------------------------------------------
_agent_instance_registry: dict[str, Agent] = {}
_agent_instance_registry_locks: dict[str, threading.Lock] = {}
_agent_instance_registry_locks_lock = threading.Lock()

_INTERNAL_TOOL_NAMES = {
    "request_help",
    "get_time_date",
    "get_current_active_agent",
    "get_supervisor_agent",
}
_INTERNAL_TOOL_PREFIXES = ("transfer_to_",)


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


def _is_internal_tool_name(name: str) -> bool:
    if name in _INTERNAL_TOOL_NAMES:
        return True
    return any(name.startswith(prefix) for prefix in _INTERNAL_TOOL_PREFIXES)


def _command_from_name(name: str) -> str:
    """Slug for the ``/<command>`` slash-command picker.

    Defers to ``Agent.validate_name`` so the slug uses the same canonicalization
    that the agent graph uses for tool / sub-agent node names (the regex
    ``[a-zA-Z0-9_-]`` plus ``__`` collapse).  Keeps everything consistent
    between the picker, the graph and the handoff tool names.
    """
    return Agent.validate_name(name.strip())


def _format_annotation(annotation: object) -> str:
    """Render a type annotation as a short human-readable string."""
    if annotation is None:
        return "Any"
    if isinstance(annotation, type):
        return annotation.__name__
    # ``typing`` generics (list[str], Optional[int], …) format reasonably
    # under ``str()``; strip the leading ``typing.`` for compactness.
    text = str(annotation)
    if text.startswith("typing."):
        text = text[len("typing."):]
    return text


def _extract_tool_parameters(tool: object) -> list[dict]:
    """Pull parameter metadata from a tool's pydantic ``args_schema``.

    Returns an empty list when the tool has no schema (e.g. a plain
    ``@tool`` decorated callable with no arguments).  Each entry exposes
    ``name``, ``type``, ``required``, ``default`` (when not required) and
    ``description``.
    """
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is None:
        return []
    model_fields = getattr(args_schema, "model_fields", None)
    if not isinstance(model_fields, dict):
        return []

    try:
        from pydantic_core import PydanticUndefined
    except ImportError:  # pragma: no cover — pydantic v2 ships pydantic_core
        PydanticUndefined = None  # type: ignore[assignment]

    params: list[dict] = []
    for field_name, field_info in model_fields.items():
        annotation = getattr(field_info, "annotation", None)
        description = getattr(field_info, "description", None) or ""
        is_required = bool(getattr(field_info, "is_required", lambda: False)())
        entry: dict = {
            "name": field_name,
            "type": _format_annotation(annotation),
            "description": description,
            "required": is_required,
        }
        if not is_required:
            default = getattr(field_info, "default", None)
            if PydanticUndefined is not None and default is PydanticUndefined:
                default_value = None
            else:
                default_value = default
            # JSON-serialize via repr fallback so weird default objects don't
            # break the response.
            try:
                import json

                json.dumps(default_value)
                entry["default"] = default_value
            except (TypeError, ValueError):
                entry["default"] = repr(default_value)
        params.append(entry)
    return params


def _get_agent_instance(class_name: str) -> Agent | None:
    """Lazily instantiate an agent class and cache the resulting instance.

    Returns ``None`` when the class is unknown or instantiation fails.
    """
    cached = _agent_instance_registry.get(class_name)
    if cached is not None:
        return cached

    with _agent_instance_registry_locks_lock:
        lock = _agent_instance_registry_locks.setdefault(class_name, threading.Lock())

    with lock:
        cached = _agent_instance_registry.get(class_name)
        if cached is not None:
            return cached

        registry = _get_agent_class_registry()
        agent_cls = registry.get(class_name)
        if agent_cls is None:
            return None

        try:
            instance = agent_cls.New()
        except Exception as exc:
            logger.warning(
                "Failed to instantiate agent %s for command extraction: %s",
                class_name,
                exc,
            )
            return None

        _agent_instance_registry[class_name] = instance
        return instance


def _instance_class_name(instance: Agent) -> str:
    cls = type(instance)
    return f"{cls.__module__}/{cls.__name__}"


def _extract_model_from_base_chat_model(base_chat_model: object) -> str | None:
    """Try the common LangChain attributes that hold the underlying model id.

    Returns ``None`` when we can't resolve it (the chat model class doesn't
    follow any known convention).  Order matters: ``model`` is the most common
    (e.g. ``ChatOpenAI``), ``model_name`` is used by older integrations,
    ``model_id`` by Bedrock / Vertex wrappers.
    """
    for attr in ("model", "model_name", "model_id"):
        value = getattr(base_chat_model, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_model_info(
    agent_cls: type | None,
    instance: Agent | None,
) -> tuple[str | None, str | None]:
    """Return ``(model_id, provider)`` for an agent.

    Prefers the live instance (instantiated via ``cls.New()``) because that's
    what the agent will actually run.  Falls back to class-level attributes
    (``cls.model`` / ``cls.provider`` — used by AbiAgent and friends) which is
    cheap and works without instantiation.
    """
    model_id: str | None = None
    provider: str | None = None

    if instance is not None:
        base_chat_model = getattr(instance, "_chat_model", None)
        if base_chat_model is None:
            base_chat_model = getattr(instance, "chat_model", None)
        if base_chat_model is not None:
            model_id = _extract_model_from_base_chat_model(base_chat_model)
        # Pydantic ChatModel wrapper (if the agent kept it) exposes ``model_id``
        # and ``provider`` directly.  Try those as a secondary source.
        if not model_id:
            wrapper_model_id = getattr(instance, "model_id", None)
            if isinstance(wrapper_model_id, str) and wrapper_model_id:
                model_id = wrapper_model_id
        wrapper_provider = getattr(instance, "provider", None)
        if isinstance(wrapper_provider, str) and wrapper_provider:
            provider = wrapper_provider

    if agent_cls is not None:
        if not model_id:
            cls_model = getattr(agent_cls, "model", None)
            if isinstance(cls_model, str) and cls_model.strip():
                model_id = cls_model
        if not provider:
            cls_provider = getattr(agent_cls, "provider", None)
            if isinstance(cls_provider, str) and cls_provider.strip():
                provider = cls_provider

    return model_id, provider


def _intent_to_payload(intent: object, owner_name: str, owner_class_name: str) -> dict[str, str] | None:
    """Normalize an ``Intent`` dataclass to a JSON-serializable dict.

    Lives outside the recursive walker so it can be reused if we ever expose
    intents from non-IntentAgent instances.  Returns ``None`` when the object
    doesn't look like an Intent.
    """
    if not hasattr(intent, "intent_value") or not hasattr(intent, "intent_type"):
        return None

    intent_type_raw = getattr(intent, "intent_type", "")
    intent_type = getattr(intent_type_raw, "value", str(intent_type_raw))
    scope_raw = getattr(intent, "intent_scope", None)
    if scope_raw is None:
        intent_scope = ""
    elif hasattr(scope_raw, "value"):
        intent_scope = scope_raw.value
    else:
        intent_scope = str(scope_raw)

    return {
        "intent_value": str(getattr(intent, "intent_value", "")),
        "intent_type": intent_type,
        "intent_target": str(getattr(intent, "intent_target", "")),
        "intent_scope": intent_scope,
        "owner_name": owner_name,
        "owner_class_name": owner_class_name,
    }


def _extract_agent_commands(
    agent_instance: Agent,
    *,
    recursive: bool = False,
    max_depth: int = 3,
) -> dict[str, list[dict[str, str]]]:
    """Extract tools, sub-agents and intents exposed by an agent instance.

    When ``recursive`` is True, descend into each sub-agent's own tools,
    sub-agents and intents so the chat composer can offer the full reachable
    command tree and route directly to the agent that owns the chosen entry.

    Each entry carries ``owner_name`` / ``owner_class_name`` identifying the
    agent instance that actually exposes the tool, sub-agent or intent.
    Sub-agent entries additionally carry ``target_name`` / ``target_class_name``
    so the frontend can redirect the chat to the sub-agent itself.
    """
    tools_payload: list[dict[str, str]] = []
    sub_agents_payload: list[dict[str, str]] = []
    intents_payload: list[dict[str, str]] = []
    seen_tool_keys: set[tuple[str, str]] = set()
    seen_subagent_keys: set[tuple[str, str]] = set()
    seen_intent_keys: set[tuple[str, str, str]] = set()
    visited_owners: set[str] = set()

    def _walk(instance: Agent, depth: int) -> None:
        owner_class_name = _instance_class_name(instance)
        if owner_class_name in visited_owners:
            return
        visited_owners.add(owner_class_name)

        owner_name = getattr(instance, "name", "") or ""

        for tool in instance.tools:
            tool_name = getattr(tool, "name", None)
            if not isinstance(tool_name, str) or not tool_name:
                continue
            if _is_internal_tool_name(tool_name):
                continue
            key = (tool_name, owner_class_name)
            if key in seen_tool_keys:
                continue
            seen_tool_keys.add(key)
            description = getattr(tool, "description", "") or ""
            tools_payload.append({
                "name": tool_name,
                "description": description,
                "command": _command_from_name(tool_name),
                "owner_name": owner_name,
                "owner_class_name": owner_class_name,
                "parameters": _extract_tool_parameters(tool),
                # ``BaseTool.return_direct`` defaults to False; surface it so
                # the UI can show whether the tool short-circuits the agent.
                "return_direct": bool(getattr(tool, "return_direct", False)),
            })

        # Intents only exist on IntentAgent (and subclasses).  Reading the
        # ``intents`` property when present avoids special-casing the class.
        instance_intents = getattr(instance, "intents", None)
        if isinstance(instance_intents, list):
            for intent in instance_intents:
                payload = _intent_to_payload(intent, owner_name, owner_class_name)
                if payload is None:
                    continue
                key_i = (payload["intent_value"], payload["intent_target"], owner_class_name)
                if key_i in seen_intent_keys:
                    continue
                seen_intent_keys.add(key_i)
                intents_payload.append(payload)

        for sub_agent in instance.agents:
            sub_name = getattr(sub_agent, "name", None)
            if not isinstance(sub_name, str) or not sub_name:
                continue
            target_class_name = _instance_class_name(sub_agent)
            key = (sub_name, owner_class_name)
            if key not in seen_subagent_keys:
                seen_subagent_keys.add(key)
                description = getattr(sub_agent, "description", "") or ""
                sub_agents_payload.append({
                    "name": sub_name,
                    "description": description,
                    "command": _command_from_name(sub_name),
                    "owner_name": owner_name,
                    "owner_class_name": owner_class_name,
                    "target_name": sub_name,
                    "target_class_name": target_class_name,
                })

            if recursive and depth + 1 < max_depth:
                _walk(sub_agent, depth + 1)

    _walk(agent_instance, depth=0)

    return {
        "tools": tools_payload,
        "sub_agents": sub_agents_payload,
        "intents": intents_payload,
    }


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
    return f"{public_api_host}/modules/{path.lstrip('/')}"


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
                module_path=getattr(agent_cls, "__module__", None),
                provider="abi",
                enabled=enabled,
                system_prompt=system_prompt,
            ),
        )
        agent_list.append(created_agent)
        existing_agents_by_class_name[class_name] = created_agent

    enriched_agent_list: list[AgentRecord] = []
    for agent in agent_list:
        suggestions = None
        logo_url = None
        intents = None
        module_path = agent.module_path
        live_model_id: str | None = None
        live_provider: str | None = None
        if agent.class_name:
            resolved_cls = class_name_to_agent_class.get(agent.class_name)
            if resolved_cls is not None and isinstance(resolved_cls, type):
                suggestions = _extract_agent_suggestions(resolved_cls)
                logo_url = getattr(resolved_cls, "logo_url", None)
                intents = _extract_agent_intents(resolved_cls)

                # Pull live model info — uses the cached instance when one
                # exists (no extra instantiation cost), otherwise falls back
                # to the class-level ``model`` / ``provider`` attributes.
                cached_instance = _agent_instance_registry.get(agent.class_name)
                live_model_id, live_provider = _extract_model_info(
                    resolved_cls, cached_instance
                )

                # Backfill module_path (persist) when missing on existing DB records.
                if not module_path:
                    module_path = getattr(resolved_cls, "__module__", None)
                    if module_path:
                        updated = await agent_service.update_agent(
                            context=request_context(current_user),
                            agent_id=agent.id,
                            updates=AgentUpdateInput(module_path=module_path),
                        )
                        if updated is not None:
                            agent = updated

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

        # Prefer the live model_id / provider over whatever was persisted, but
        # keep the DB values when no live source is available.
        merged_model_id = live_model_id or agent.model_id
        merged_provider = live_provider or agent.provider

        enriched_agent_list.append(
            replace(
                agent,
                module_path=module_path,
                suggestions=suggestions,
                logo_url=logo_url,
                intents=intents,
                model_id=merged_model_id,
                provider=merged_provider,
            )
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


@router.get("/{agent_id}/commands")
async def get_agent_commands(
    agent_id: str,
    recursive: bool = False,
    max_depth: int = 3,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> dict:
    """Return the tools, sub-agents, intents and model info for an agent.

    When ``recursive`` is true, the response includes tools and sub-agents
    reachable through descendant sub-agents (capped by ``max_depth``).  Each
    entry exposes ``name``, ``description``, a ``command`` slug, and the
    ``owner_*`` / ``target_*`` identifiers needed for the chat composer to
    redirect directly to the agent that owns the entry.
    """
    agent = await agent_service.get_agent(
        context=request_context(current_user),
        agent_id=agent_id,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await require_workspace_access(current_user.id, agent.workspace_id)

    empty: dict = {
        "tools": [],
        "sub_agents": [],
        "intents": [],
        "model_id": None,
        "provider": None,
    }

    if not agent.class_name:
        return empty

    instance = _get_agent_instance(agent.class_name)
    if instance is None:
        return empty

    payload = _extract_agent_commands(
        instance,
        recursive=recursive,
        max_depth=max(1, min(max_depth, 5)),
    )

    registry = _get_agent_class_registry()
    resolved_cls = registry.get(agent.class_name)
    model_id, provider = _extract_model_info(resolved_cls, instance)
    payload["model_id"] = model_id
    payload["provider"] = provider
    return payload
