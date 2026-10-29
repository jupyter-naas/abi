"""Agents FastAPI primary adapter."""

from __future__ import annotations

import asyncio
import threading
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.agent_feature_access import (
    caller_feature_flags,
    feature_keys_of,
    filter_feature_agents,
)
from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
    resolve_agent_ref,
)
from naas_abi.apps.nexus.apps.api.app.services.agents import (
    AgentCreateInput,
    AgentRecord,
    AgentService,
    AgentUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import (
    REMOTE_PROVIDER,
    RemoteAgent,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.scopes import (
    agent_class_label,
    agent_scope,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares
from naas_abi.apps.nexus.apps.api.app.services.registry import (
    ServiceRegistry,
    get_service_registry,
)
from naas_abi.apps.nexus.apps.api.app.utils.public_urls import (
    public_modules_url,
    resolve_abi_module_path,
    resolve_module_public_asset_path,
)
from naas_abi_core import logger
from naas_abi_core.services.agent.Agent import Agent
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

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
# Registry key -> the engine module that loads the class (its configured path):
# the ``<module>`` of the agent's module scope.
_agent_class_modules: dict[str, str] = {}
_agent_class_registry_lock = threading.Lock()

# Serialize POST /sync per workspace inside one API worker. Cross-worker races
# are blocked by uq_agent_configs_workspace_class_name (migration 0041).
_workspace_sync_locks: dict[str, asyncio.Lock] = {}
_workspace_sync_locks_guard = threading.Lock()


def _workspace_sync_lock(workspace_id: str) -> asyncio.Lock:
    with _workspace_sync_locks_guard:
        lock = _workspace_sync_locks.get(workspace_id)
        if lock is None:
            lock = asyncio.Lock()
            _workspace_sync_locks[workspace_id] = lock
        return lock


def _canonical_agent_sort_key(agent: AgentRecord) -> tuple:
    """Prefer default, then the oldest row when collapsing duplicates."""
    return (
        0 if agent.is_default else 1,
        agent.created_at,
        agent.id,
    )


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
        owners: dict[type, str] = dict.fromkeys(abi_module.agents, type(abi_module).__module__)

        for module_key, module in abi_module.engine.modules.items():
            for agent_cls in module.agents:
                if agent_cls is None:
                    continue
                candidate_classes.append(agent_cls)
                owners.setdefault(agent_cls, module_key)

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
        _agent_class_modules.update(
            {key: owners[cls] for key, cls in registry.items() if cls in owners}
        )
        _agent_class_registry = registry
        return _agent_class_registry


def agent_class_modules() -> dict[str, str]:
    """Registry key -> the engine module that loads the class."""
    _get_agent_class_registry()
    return _agent_class_modules


class AgentsFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


def get_agent_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> AgentService:
    return registry.agents


async def _workspace_slug(workspace_id: str) -> str | None:
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.models import WorkspaceModel

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkspaceModel.slug).where(WorkspaceModel.id == workspace_id)
        )
        return result.scalar_one_or_none()


async def _visible_to_caller(
    agents: list[AgentRecord], current_user: User, workspace_id: str
) -> list[AgentRecord]:
    """The agents of ``workspace_id`` the caller may use: a module's agent needs
    its module scope (``module:UseAgent``), an office agent its feature too. IAM
    alone decides: there is no set and no on/off switch."""
    flags = await caller_feature_flags(current_user, workspace_id, feature_keys_of(agents))
    classes = _get_agent_class_registry()

    def scope_of(agent: AgentRecord) -> ModuleScope | None:
        return agent_scope(agent, classes, _agent_class_modules)

    return await authz.filter_scopes(
        filter_feature_agents(agents, flags),
        user=current_user,
        workspace=workspace_id,
        scope_of=scope_of,
    )


async def _served(agents: list[AgentRecord]) -> list[AgentRecord]:
    """``agents`` but the remote ones whose module is not READY (discovery does
    not list them); all of them when discovery cannot be read."""
    if not any(agent.provider == REMOTE_PROVIDER for agent in agents):
        return agents
    remote = await _discovered_remote_agents()
    if remote is None:
        return agents
    served = {agent.key for agent in remote}
    return [
        agent for agent in agents if agent.provider != REMOTE_PROVIDER or agent.class_name in served
    ]


async def _workspace_catalog_seed(workspace_id: str) -> dict | None:
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.core.workspace_seed_catalog import parse_catalog_seed
    from naas_abi.apps.nexus.apps.api.app.models import WorkspaceModel

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkspaceModel.catalog_seed).where(WorkspaceModel.id == workspace_id)
        )
        raw = result.scalar_one_or_none()
    return parse_catalog_seed(raw)


def _get_engine_default_agent_class_name() -> str | None:
    """Resolve engine ``default_agent`` (e.g. ``myapp MyAgent``) to a registry key.

    Registry keys are ``{python_module}/{ClassName}`` (for example
    ``myapp.agents.MyAgent/MyAgent``). The config form is ``{module} {AgentName}``,
    so we match by scanning the live class registry rather than inventing a path.
    """
    try:
        from naas_abi import ABIModule

        default_agent = ABIModule.get_instance().engine.configuration.default_agent
        if not default_agent or " " not in default_agent.strip():
            return None
        module_name, agent_name = default_agent.strip().split(" ", 1)
        if not module_name or not agent_name:
            return None

        registry = _get_agent_class_registry()
        suffix = f"/{agent_name}"
        # Prefer an exact class-name suffix under the configured module package.
        for class_name in registry:
            if not class_name.endswith(suffix):
                continue
            if class_name == f"{module_name}/{agent_name}" or class_name.startswith(
                f"{module_name}."
            ):
                return class_name
        # Fallback: unique class-name match across modules.
        matches = [key for key in registry if key.endswith(suffix)]
        if len(matches) == 1:
            return matches[0]
    except Exception:
        logger.debug("Could not resolve engine default_agent", exc_info=True)
    return None


def _resolve_workspace_default_class_name(
    known_class_names: Mapping[str, Any],
) -> str | None:
    """Workspace chat default: engine ``default_agent``, then naas_abi Abi."""
    resolved = _get_engine_default_agent_class_name()
    if resolved:
        return resolved
    return _nexus_abi_class_name(known_class_names)


def pick_workspace_chat_agent_id(
    agents: list[AgentRecord],
    requested_id: str | None,
) -> str | None:
    """Use the requested agent only if it is among ``agents``, the ones the caller
    may use in this workspace.

    A leftover picker id from another workspace (or an agent the caller may not
    use) must not run. Fall back to the workspace default, then Abi (the Nexus
    orchestrator), then the first usable agent.
    """
    if requested_id:
        requested = next((agent for agent in agents if agent.id == requested_id), None)
        if requested is not None:
            return requested.id
    default = next((agent for agent in agents if agent.is_default), None)
    if default is not None:
        return default.id
    abi = next((agent for agent in agents if _is_nexus_abi_agent(agent)), None)
    if abi is not None:
        return abi.id
    return agents[0].id if agents else None


def _is_nexus_abi_agent(agent: AgentRecord) -> bool:
    """True for the naas_abi AbiAgent, not an AbiAgent class from another module."""
    class_name = agent.class_name or ""
    return class_name.endswith("/AbiAgent") and class_name.startswith("naas_abi.")


def _is_nexus_slides_agent(agent: AgentRecord) -> bool:
    """True for the Nexus office Slides agent, not other office writers."""
    if agent.name == "Slides":
        return True
    class_name = agent.class_name or ""
    return class_name.endswith("/SlidesAgent") and "naas_abi" in class_name


def pick_workspace_slides_agent_id(agents: list[AgentRecord]) -> str | None:
    """The Nexus Slides row among ``agents`` (those the caller may use), or None.

    Open-deck turns bind this agent. The workspace default stays the
    orchestrator for ordinary chat. A missing row is not a fallback to Abi.
    """
    for agent in agents:
        if _is_nexus_slides_agent(agent):
            return agent.id
    return None


def _is_nexus_documents_agent(agent: AgentRecord) -> bool:
    if agent.name == "Documents":
        return True
    class_name = agent.class_name or ""
    return class_name.endswith("/DocumentsAgent") and "naas_abi" in class_name


def pick_workspace_documents_agent_id(agents: list[AgentRecord]) -> str | None:
    """The Nexus Documents row among ``agents`` (those the caller may use), or None."""
    for agent in agents:
        if _is_nexus_documents_agent(agent):
            return agent.id
    return None


def _is_nexus_sheets_agent(agent: AgentRecord) -> bool:
    if agent.name == "Sheets":
        return True
    class_name = agent.class_name or ""
    return class_name.endswith("/SheetsAgent") and "naas_abi" in class_name


def pick_workspace_sheets_agent_id(agents: list[AgentRecord]) -> str | None:
    """The Nexus Sheets row among ``agents`` (those the caller may use), or None."""
    for agent in agents:
        if _is_nexus_sheets_agent(agent):
            return agent.id
    return None


def _nexus_abi_class_name(class_names: Iterable[str]) -> str | None:
    """Registry key of the naas_abi Abi orchestrator, when the engine loaded it.

    Matched the same way as ``_is_nexus_abi_agent`` so an ``AbiAgent`` from
    another module is never mistaken for the platform orchestrator.
    """
    return next(
        (
            class_name
            for class_name in class_names
            if class_name.endswith("/AbiAgent") and class_name.startswith("naas_abi.")
        ),
        None,
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
    return agent_class_label(agent_cls)


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


def _class_declared_model_ids(agent_cls: type | None) -> list[str]:
    """Chat model ids the agent class can load (``get_chat_model_ids`` / ``MODEL_IDS``)."""
    if agent_cls is None:
        return []
    getter = getattr(agent_cls, "get_chat_model_ids", None)
    if callable(getter):
        try:
            ids = getter()
        except Exception:
            ids = None
        if isinstance(ids, (list, tuple)):
            return [str(item).strip() for item in ids if str(item).strip()]
    attr = getattr(agent_cls, "MODEL_IDS", None)
    if isinstance(attr, (list, tuple)):
        return [str(item).strip() for item in attr if str(item).strip()]
    single = _class_declared_model_id(agent_cls)
    return [single] if single else []


def _class_declared_model_id(agent_cls: type | None) -> str | None:
    """Model id declared by the agent class via ``get_chat_model_id``.

    This is the authoritative model for class-backed (ABI) agents : it mirrors
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
    if agent.provider == REMOTE_PROVIDER:
        # Its module picks the model; the engine default would be a guess.
        return None

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
    attach the class display name, suggestions, logo, intents, a derived
    ``module_path`` and the resolved model id.  Performs no database writes :
    any missing ``module_path`` is only derived in-memory here; persistence of
    that backfill, and of a renamed class label, happens in
    :func:`_reconcile_workspace_agents`.
    """
    suggestions = None
    logo_url = None
    intents = None
    display_name = None
    resolved_cls: type | None = None
    module_path = agent.module_path
    if agent.class_name:
        resolved_cls = class_name_to_agent_class.get(agent.class_name)
        if resolved_cls is not None and isinstance(resolved_cls, type):
            suggestions = _extract_agent_suggestions(resolved_cls)
            logo_url = getattr(resolved_cls, "logo_url", None)
            intents = _extract_agent_intents(resolved_cls)
            display_name = _get_agent_class_name(resolved_cls)
            if not module_path:
                module_path = getattr(resolved_cls, "__module__", None)

    # If module_path is still missing but class_name is available, derive it from class_name.
    if not module_path and agent.class_name and "/" in agent.class_name:
        module_path = agent.class_name.split("/", 1)[0] or None

    # Normalize logo_url to be module-relative, then convert to public /modules URL.
    if isinstance(logo_url, str) and logo_url:
        if not (logo_url.startswith("http://") or logo_url.startswith("https://")):
            abi_module_path = resolve_abi_module_path(module_path)
            normalized_path = resolve_module_public_asset_path(
                logo_url,
                abi_module_path=abi_module_path,
            )
            logo_url = public_modules_url(normalized_path)

    return replace(
        agent,
        name=display_name or agent.name,
        module_path=module_path,
        suggestions=suggestions,
        logo_url=logo_url,
        intents=intents,
        resolved_model_id=_resolve_agent_model_id(agent, resolved_cls),
        model_ids=_class_declared_model_ids(resolved_cls) or None,
    )


async def _dedupe_agents_by_class_name(
    agent_service: AgentService,
    agent_list: list[AgentRecord],
) -> list[AgentRecord]:
    """Keep one row per non-empty class_name; delete the rest.

    Prefer is_default, then the oldest created_at. Manual agents with
    no class_name are left alone (multiple custom rows are allowed).
    """
    by_class: dict[str, list[AgentRecord]] = defaultdict(list)
    passthrough: list[AgentRecord] = []
    for agent in agent_list:
        if agent.class_name:
            by_class[agent.class_name].append(agent)
        else:
            passthrough.append(agent)

    kept: list[AgentRecord] = list(passthrough)
    for class_name, rows in by_class.items():
        if len(rows) == 1:
            kept.append(rows[0])
            continue
        rows_sorted = sorted(rows, key=_canonical_agent_sort_key)
        canonical = rows_sorted[0]
        kept.append(canonical)
        for duplicate in rows_sorted[1:]:
            logger.warning(
                "Removing duplicate agent_configs row workspace=%s class_name=%s id=%s keep=%s",
                duplicate.workspace_id,
                class_name,
                duplicate.id,
                canonical.id,
            )
            await agent_service.delete_agent(agent_id=duplicate.id)
    return kept


async def _discovered_remote_agents() -> list[RemoteAgent] | None:
    """Agents published through NATS discovery; None when discovery cannot be read."""
    from naas_abi.apps.nexus.apps.api.app.services.agents.remote import factory

    try:
        return await factory.get_remote_agent_directory().list_agents()
    except Exception as exc:  # noqa: BLE001 - keep remote rows untouched on any error
        logger.warning("Remote agent discovery unavailable, leaving remote agents as is: %s", exc)
        return None


async def _reconcile_workspace_agents(
    agent_service: AgentService,
    workspace_id: str,
    agent_list: list[AgentRecord],
    class_name_to_agent_class: dict[str, type[Agent]],
    remote_agents: list[RemoteAgent] | None = None,
) -> list[AgentRecord]:
    """Reconcile persisted agent records with the code class registry.

    Mutating counterpart to the read-only listing:

    * **Deduplicate** rows that share the same ``class_name`` (legacy race).
    * **Prune** stale agents : records whose ``class_name`` is no longer present
      in the registry (their module/code was removed).  Agents without a
      ``class_name`` (e.g. manually created ones) are left untouched.
    * **Create** records for newly discovered agent classes (idempotent under
      the partial unique index on workspace_id + class_name).
    * **Backfill** a missing ``module_path`` on existing records.
    * **Mark** the workspace default (its seed's ``default_agent``, else the
      engine's ``default_agent``, else Abi).
    * **Remote agents** (``remote_agents``, from NATS discovery) get rows with
      ``provider="remote"`` and ``class_name="<module_id>/<Agent>"``, kept while
      their module is not READY (the listing leaves them out meanwhile,
      ``_served``).

    The rows hold no on/off state: who uses each agent is IAM's
    (``module:UseAgent`` on its module scope), decided where it is listed or used.

    Returns the reconciled agent list (deleted records removed, created ones
    appended, backfilled ones refreshed).
    """
    agent_list = await _dedupe_agents_by_class_name(agent_service, agent_list)
    existing_agents_by_class_name = {
        agent.class_name: agent for agent in agent_list if agent.class_name
    }

    # Prune agents persisted from a class that no longer exists in the registry.
    stale_agents = [
        agent
        for agent in agent_list
        if agent.class_name
        and agent.provider != REMOTE_PROVIDER
        and agent.class_name not in class_name_to_agent_class
    ]
    for agent in stale_agents:
        logger.debug("Removing stale agent (class no longer in registry): %s", agent.class_name)
        await agent_service.delete_agent(agent_id=agent.id)
        existing_agents_by_class_name.pop(agent.class_name, None)
    if stale_agents:
        stale_ids = {agent.id for agent in stale_agents}
        agent_list = [agent for agent in agent_list if agent.id not in stale_ids]

    remote_by_class_name = {agent.key: agent for agent in remote_agents or ()}
    # Workspace refs ("module Agent") resolve against in-process and remote agents.
    known_class_names = {**class_name_to_agent_class, **dict.fromkeys(remote_by_class_name)}

    slug = await _workspace_slug(workspace_id)
    catalog_seed = await _workspace_catalog_seed(workspace_id)
    from naas_abi.apps.nexus.apps.api.app.core.workspace_seed_catalog import (
        effective_seed_default_agent,
    )

    default_class_name = _resolve_workspace_default_class_name(known_class_names)
    seed_default_ref = effective_seed_default_agent(slug, catalog_seed)
    if seed_default_ref:
        seed_default = resolve_agent_ref(seed_default_ref, known_class_names)
        if seed_default:
            default_class_name = seed_default

    # Persist any newly discovered agent classes to the database.
    for class_name, agent_cls in class_name_to_agent_class.items():
        if class_name in existing_agents_by_class_name:
            continue

        name = _get_agent_class_name(agent_cls)
        description = _get_agent_class_description(agent_cls)

        logger.debug("Creating agent in nexus backend: {}", name)
        system_prompt = _get_agent_system_prompt(agent_cls)
        try:
            created_agent = await agent_service.create_agent(
                data=AgentCreateInput(
                    name=name,
                    description=description or "",
                    workspace_id=workspace_id,
                    class_name=class_name,
                    module_path=getattr(agent_cls, "__module__", None),
                    provider="abi",
                    system_prompt=system_prompt,
                ),
            )
        except IntegrityError:
            # Another concurrent sync won the insert (unique index). Re-read.
            logger.info(
                "Agent sync race lost for workspace=%s class_name=%s; reloading row",
                workspace_id,
                class_name,
            )
            refreshed = await agent_service.list_workspace_agents(
                workspace_id=workspace_id,
            )
            created_agent = next(
                (agent for agent in refreshed if agent.class_name == class_name),
                None,
            )
            if created_agent is None:
                raise
            existing_agents_by_class_name[class_name] = created_agent
            if not any(agent.id == created_agent.id for agent in agent_list):
                agent_list.append(created_agent)
            continue

        if default_class_name and class_name == default_class_name:
            updated = await agent_service.update_agent(
                agent_id=created_agent.id,
                updates=AgentUpdateInput(is_default=True),
            )
            if updated is not None:
                created_agent = updated
        agent_list.append(created_agent)
        existing_agents_by_class_name[class_name] = created_agent

    for class_name, remote in remote_by_class_name.items():
        if class_name in existing_agents_by_class_name:
            continue
        try:
            created_agent = await agent_service.create_agent(
                data=AgentCreateInput(
                    name=remote.name,
                    description=remote.description,
                    workspace_id=workspace_id,
                    class_name=class_name,
                    module_path=remote.module_id,
                    provider=REMOTE_PROVIDER,
                ),
            )
        except IntegrityError:
            logger.info(
                "Remote agent sync race lost for workspace=%s class_name=%s; skipping",
                workspace_id,
                class_name,
            )
            continue
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
                    agent_id=agent.id,
                    updates=AgentUpdateInput(module_path=module_path),
                )
                if updated is not None:
                    reconciled.append(updated)
                    continue
        reconciled.append(agent)

    # The picker reads the stored name. A class rename would otherwise stay
    # stuck on the row created under the old name.
    renamed: list[AgentRecord] = []
    for agent in reconciled:
        resolved_cls = class_name_to_agent_class.get(agent.class_name) if agent.class_name else None
        class_label = _get_agent_class_name(resolved_cls) if resolved_cls is not None else None
        if not class_label or agent.name == class_label:
            renamed.append(agent)
            continue
        updated = await agent_service.update_agent(
            agent_id=agent.id,
            updates=AgentUpdateInput(name=class_label),
        )
        renamed.append(updated if updated is not None else agent)
    reconciled = renamed

    # Ensure the workspace (or engine) default agent is marked.
    if default_class_name:
        default_agent = next(
            (agent for agent in reconciled if agent.class_name == default_class_name),
            None,
        )
        if default_agent and not default_agent.is_default:
            updated = await agent_service.update_agent(
                agent_id=default_agent.id,
                updates=AgentUpdateInput(is_default=True),
            )
            if updated is not None:
                reconciled = [updated if agent.id == updated.id else agent for agent in reconciled]

    return reconciled


async def workspace_roster(agent_service: AgentService, workspace_id: str) -> list[AgentRecord]:
    """The workspace's agent rows, seeded from the modules when there are none yet
    (a workspace whose roster no listing reconciled): a chat or ``/v1`` turn binds
    the agents it may run from it, and an empty roster would refuse every one.
    Seeding is the platform's own reconciliation, not a change of the caller's."""
    agent_list = await agent_service.list_workspace_agents(workspace_id=workspace_id)
    if agent_list:
        return agent_list
    async with _workspace_sync_lock(workspace_id):
        agent_list = await agent_service.list_workspace_agents(workspace_id=workspace_id)
        if agent_list:
            return agent_list
        try:
            classes = _get_agent_class_registry()
        except Exception:  # noqa: BLE001 - no engine loaded: no module agent to seed
            logger.warning("No agent registry to seed workspace=%s", workspace_id, exc_info=True)
            return agent_list
        logger.info("Seeding the empty agent roster of workspace=%s for a turn", workspace_id)
        return await _reconcile_workspace_agents(
            agent_service=agent_service,
            workspace_id=workspace_id,
            agent_list=agent_list,
            class_name_to_agent_class=classes,
            remote_agents=await _discovered_remote_agents(),
        )


async def _enriched_workspace_agents(
    *,
    workspace_id: str,
    current_user: User,
    agent_service: AgentService,
    may_sync: bool,
    always_reconcile: bool,
) -> list[AgentRecord]:
    """Load workspace agents, optionally reconcile, enrich, and apply feature scoping.

    ``may_sync`` is the caller's right to change the roster: without it the
    listing is returned as stored, whatever ``always_reconcile`` says.
    """
    class_name_to_agent_class = _get_agent_class_registry()

    async with _workspace_sync_lock(workspace_id):
        agent_list = await agent_service.list_workspace_agents(workspace_id=workspace_id)
        if may_sync and (always_reconcile or not agent_list):
            if not agent_list:
                logger.info(
                    "Auto-reconciling empty agent roster for workspace=%s",
                    workspace_id,
                )
            agent_list = await _reconcile_workspace_agents(
                agent_service=agent_service,
                workspace_id=workspace_id,
                agent_list=agent_list,
                class_name_to_agent_class=class_name_to_agent_class,
                remote_agents=await _discovered_remote_agents(),
            )

    return [
        _enrich_agent(agent, class_name_to_agent_class)
        for agent in await _visible_to_caller(await _served(agent_list), current_user, workspace_id)
    ]


async def seed_workspace_agents(
    *,
    workspace_id: str,
    current_user: User,
    agent_service: AgentService,
) -> None:
    """Populate ``agent_configs`` when a workspace is first created.

    The caller just created the workspace (``CreateWorkspace`` was decided), so
    the roster is theirs to seed.
    """
    await _enriched_workspace_agents(
        workspace_id=workspace_id,
        current_user=current_user,
        agent_service=agent_service,
        may_sync=True,
        always_reconcile=True,
    )


@router.get("/", dependencies=[declares("ListAgents")])
async def list_agents(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> list[AgentRecord]:
    """List a workspace's persisted agents, enriched for display.

    Exactly the agents the caller may use: a module's agent the user holds no
    module scope for (``module:UseAgent`` in the workspace) is left out, and so
    are the naas_abi office agents of a feature this user cannot open (see
    ``core.agent_feature_access``), so two members of one workspace can get
    different rosters. A remote agent is listed while its module is READY.

    When the workspace has no persisted agent rows yet, reconciles once with
    the code class registry (same work as ``POST /sync``) before returning,
    if the caller may sync agents.
    Use ``POST /sync`` when config rosters change and rows already exist.
    """
    if not workspace_id:
        return []

    await authz.require("ListAgents", user=current_user, workspace=workspace_id, id="-")
    may_sync = await authz.allowed("SyncAgents", user=current_user, workspace=workspace_id, id="-")
    return await _enriched_workspace_agents(
        workspace_id=workspace_id,
        current_user=current_user,
        agent_service=agent_service,
        may_sync=may_sync,
        always_reconcile=False,
    )


@router.post("/sync", dependencies=[declares("SyncAgents"), declares("ListAgents")])
async def sync_agents(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> list[AgentRecord]:
    """Reconcile a workspace's persisted agents with the code class registry.

    Creates records for newly discovered agent classes, deletes stale ones whose
    class no longer exists in the registry, and backfills missing metadata : then
    returns the reconciled, enriched list.

    Reconciliation is workspace-wide, but the list returned is what the caller
    may use, exactly like ``GET /``. A member syncing the workspace therefore
    never narrows what an owner sees.

    A caller who may list agents but not change them (a viewer) gets the
    listing without any reconciliation: clients send this once per session
    for every role.
    """
    if not workspace_id:
        return []

    await authz.require("ListAgents", user=current_user, workspace=workspace_id, id="-")
    may_sync = await authz.allowed("SyncAgents", user=current_user, workspace=workspace_id, id="-")
    return await _enriched_workspace_agents(
        workspace_id=workspace_id,
        current_user=current_user,
        agent_service=agent_service,
        may_sync=may_sync,
        always_reconcile=True,
    )


@router.post("/", dependencies=[declares("CreateAgent")])
async def create_agent(
    agent: AgentCreateInput,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    await authz.require("CreateAgent", user=current_user, workspace=agent.workspace_id, id="-")
    created_agent = await agent_service.create_agent(data=agent)
    logger.debug("Agent created: %s", created_agent)
    return created_agent


async def _load_agent(
    agent_service: AgentService, current_user: User, action: str, agent_id: str
) -> AgentRecord:
    """The agent, once the caller may perform ``action`` on it in its workspace."""
    agent = await agent_service.get_agent(agent_id=agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await authz.require(action, user=current_user, workspace=agent.workspace_id, id=agent.id)
    return agent


@router.patch("/{agent_id}", dependencies=[declares("UpdateAgent")])
async def update_agent(
    agent_id: str,
    updates: AgentUpdateInput,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    await _load_agent(agent_service, current_user, "UpdateAgent", agent_id)
    updated_agent = await agent_service.update_agent(
        agent_id=agent_id,
        updates=AgentUpdateInput(
            name=updates.name,
            description=updates.description,
            system_prompt=updates.system_prompt,
            model_id=updates.model,
            is_default=updates.is_default,
        ),
    )
    if updated_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return updated_agent


@router.delete("/{agent_id}", dependencies=[declares("DeleteAgent")])
async def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> dict[str, str]:
    await _load_agent(agent_service, current_user, "DeleteAgent", agent_id)
    await agent_service.delete_agent(agent_id=agent_id)
    return {"status": "deleted"}


@router.get("/{agent_id}", dependencies=[declares("GetAgent")])
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    agent = await _load_agent(agent_service, current_user, "GetAgent", agent_id)
    # Same rule as the listing: an agent the caller may not use (its module
    # scope, an office agent's feature) is not addressable by id either, or the
    # gate would only hide it.
    if not await _visible_to_caller([agent], current_user, agent.workspace_id):
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
