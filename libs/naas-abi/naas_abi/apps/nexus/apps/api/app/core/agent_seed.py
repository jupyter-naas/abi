"""
Seed ABI agent classes into the database for every workspace.

Called once during app startup (after workspace seeds). Builds the in-process
agent class registry and upserts each agent record per workspace:
  - creates a new row for newly discovered agent classes
  - updates metadata (name, description, logo_url, module_path, suggestions,
    intents) for existing rows whose class_name already has a DB entry

Fields owned by users (enabled, system_prompt, model_id) are never overwritten
by the seeding pass.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.core.database import async_engine
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.models import AgentConfigModel, WorkspaceModel
from naas_abi_core.services.agent.Agent import Agent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Process-level agent class registry cache (shared with the FastAPI adapter)
# ---------------------------------------------------------------------------
_agent_class_registry: dict[str, type[Agent]] | None = None
_agent_class_registry_lock = threading.Lock()


def get_agent_class_registry() -> dict[str, type[Agent]]:
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
                    "Skipping agent %s: no resolvable name (set class attribute 'name' or 'NAME')",
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


# ---------------------------------------------------------------------------
# Metadata extraction helpers
# ---------------------------------------------------------------------------


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
    return normalized or None


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
        intent_payload["intent_scope"] = (
            scope.value if scope is not None and hasattr(scope, "value") else str(scope or "")
        )
        output.append(intent_payload)

    return output or None


def _get_raw_logo_url(agent_cls: type) -> str | None:
    """Return the raw logo_url from the agent class (file path, not a public URL)."""
    return getattr(agent_cls, "logo_url", None) or None


# ---------------------------------------------------------------------------
# Per-workspace upsert
# ---------------------------------------------------------------------------


async def _upsert_agents_for_workspace(
    session: AsyncSession,
    workspace_id: str,
    registry: dict[str, type[Agent]],
) -> tuple[int, int]:
    """Create or update agent records for one workspace. Returns (created, updated)."""
    result = await session.execute(
        select(AgentConfigModel).where(AgentConfigModel.workspace_id == workspace_id)
    )
    existing: dict[str, AgentConfigModel] = {
        str(row.class_name): row
        for row in result.scalars().all()
        if row.class_name
    }

    now = datetime.now(UTC).replace(tzinfo=None)
    created = 0
    updated = 0

    for class_name, agent_cls in registry.items():
        name = _get_agent_class_name(agent_cls)
        if not name:
            continue

        description = _get_agent_class_description(agent_cls) or ""
        module_path = getattr(agent_cls, "__module__", None)
        logo_url = _get_raw_logo_url(agent_cls)
        suggestions = _extract_agent_suggestions(agent_cls)
        intents = _extract_agent_intents(agent_cls)

        if class_name in existing:
            row = existing[class_name]
            row.name = name
            row.description = description
            row.module_path = module_path
            row.logo_url = logo_url
            row.suggestions = suggestions
            row.intents = intents
            row.updated_at = now
            updated += 1
        else:
            system_prompt = _get_agent_system_prompt(agent_cls)
            enabled = name == "Abi"
            session.add(
                AgentConfigModel(
                    id=f"agent-{uuid4()}",
                    workspace_id=workspace_id,
                    name=name,
                    description=description,
                    class_name=class_name,
                    module_path=module_path,
                    provider="abi",
                    logo_url=logo_url,
                    suggestions=suggestions,
                    intents=intents,
                    system_prompt=system_prompt,
                    enabled=enabled,
                    created_at=now,
                    updated_at=now,
                )
            )
            created += 1

    return created, updated


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def seed_abi_agents() -> None:
    """Upsert ABI agent metadata for every workspace in the database.

    Runs at app startup after workspace seeds so new agent classes are visible
    immediately and changed metadata (logo, suggestions, intents, …) is
    propagated without any request-time DB writes.
    """
    try:
        loop = asyncio.get_running_loop()
        registry = await loop.run_in_executor(None, get_agent_class_registry)
    except Exception:
        logger.exception("Failed to build agent class registry — skipping agent seed")
        return

    async_session = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        ws_result = await session.execute(select(WorkspaceModel.id))
        workspace_ids: list[str] = [str(row[0]) for row in ws_result.fetchall()]

    if not workspace_ids:
        logger.info("No workspaces found; skipping agent seed")
        return

    total_created = 0
    total_updated = 0

    async with async_session() as session:
        async with session.begin():
            for workspace_id in workspace_ids:
                created, updated = await _upsert_agents_for_workspace(
                    session, workspace_id, registry
                )
                total_created += created
                total_updated += updated

    logger.info(
        "Agent seed complete: %d workspaces, %d created, %d updated",
        len(workspace_ids),
        total_created,
        total_updated,
    )
