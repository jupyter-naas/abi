"""AgentCatalogAgent tools for Settings > Agents.

Reads go through the same registry service as ``/api/agents`` (IAM scope +
workspace access), on a session bound the way the HTTP layer binds one.
``list_agent_classes`` shows the code-registered agents a workspace can put
on its roster (``agents:`` in config.yaml, form ``"<module> <ClassName>"``).
The agent open on ``/settings/agents/<id>`` arrives as the open feature
resource (kind ``agent``).

Skills have their own office agent: see ``skills_tools``.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.feature.context import active_feature_resource_id
from naas_abi.agents.feature.runtime import (
    bound_session,
    clip,
    guarded,
    jsonable,
    matches,
    request_context,
    require_member,
    run_db,
    tool_context,
)

AGENT_RESOURCE_KIND = "agent"
_FEATURE = "Agent Catalog"


def _registry() -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry

    return ServiceRegistry.instance()


async def _workspace_agents(db: Any, user_id: str, workspace_id: str) -> Any:
    """The roster this caller may see, filtered like ``GET /api/agents``.

    Without the filter the catalog would name the office agents of sections
    this role cannot open, which the HTTP listing hides.
    """
    from naas_abi.apps.nexus.apps.api.app.core.agent_feature_access import (
        caller_feature_flags,
        filter_feature_agents,
    )

    role = await require_member(db, user_id, workspace_id)
    if isinstance(role, dict):
        return role
    with bound_session(db):
        agents = await _registry().agents.list_workspace_agents(
            request_context(user_id), workspace_id
        )
    flags = await caller_feature_flags(db, workspace_id, role)
    return filter_feature_agents(agents, flags)


def _agent_row(agent: Any) -> dict[str, Any]:
    return {
        "id": agent.id,
        "name": agent.name,
        "class_name": agent.class_name,
        "enabled": agent.enabled,
        "is_default": agent.is_default,
        "model": agent.model_id,
        "description": clip(agent.description, 200),
    }


def agent_catalog_tools() -> list[BaseTool]:
    @tool
    def list_workspace_agents(query: str = "") -> Any:
        """Agents on this workspace's roster: name, class_name, enabled,
        is_default (the main chat orchestrator), model."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx

        async def _run(db: Any) -> Any:
            agents = await _workspace_agents(db, user_id, workspace_id)
            if isinstance(agents, dict):
                return agents
            rows = [
                _agent_row(a)
                for a in agents
                if matches(query, a.name, a.class_name, a.description)
            ]
            out: dict[str, Any] = {"total": len(rows), "agents": rows}
            if not agents:
                out["note"] = (
                    "No agent rows for this workspace yet. Rows are created from the "
                    "config roster by POST /api/agents/sync, which the chat and "
                    "Settings > Agents run when they load."
                )
            return out

        return guarded(_FEATURE, lambda: run_db(_run))

    @tool
    def get_workspace_agent(agent: str = "") -> Any:
        """One roster agent by id or name: description, class, model,
        suggestions, intents, and a system prompt preview. Omit agent to use
        the one open in Settings > Agents."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        wanted = (agent or "").strip() or active_feature_resource_id(
            AGENT_RESOURCE_KIND
        )
        if not wanted:
            return {"error": "No agent is open. Pass agent (id or name)."}

        async def _run(db: Any) -> Any:
            agents = await _workspace_agents(db, user_id, workspace_id)
            if isinstance(agents, dict):
                return agents
            found = next(
                (
                    a
                    for a in agents
                    if a.id == wanted or a.name.lower() == wanted.lower()
                ),
                None,
            )
            if found is None:
                return {
                    "error": f"No agent {wanted} on this roster. See list_workspace_agents."
                }
            out = _agent_row(found)
            out.update(
                {
                    "description": clip(found.description, 800),
                    "module_path": found.module_path,
                    "provider": found.provider,
                    "suggestions": jsonable(found.suggestions or [])[:6],
                    "intents": len(found.intents or []),
                    "system_prompt_preview": clip(found.system_prompt, 800),
                }
            )
            return out

        return guarded(_FEATURE, lambda: run_db(_run))

    @tool
    def list_agent_classes(query: str = "") -> Any:
        """Code-registered agent classes a workspace can add to its roster.

        Each row gives the roster ref ("<module> <ClassName>") to put under
        the workspace's agents: list in config.yaml.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx

        def _run() -> Any:
            from naas_abi import ABIModule

            abi_module = ABIModule.get_instance()
            modules = [("naas_abi", abi_module)] + [
                (name, module)
                for name, module in abi_module.engine.modules.items()
                if module is not abi_module
            ]
            seen: set[str] = set()
            rows: list[dict[str, str]] = []
            for module_name, module in modules:
                for agent_cls in getattr(module, "agents", []) or []:
                    ref = f"{module_name} {agent_cls.__name__}"
                    if ref in seen:
                        continue
                    seen.add(ref)
                    name = str(getattr(agent_cls, "name", agent_cls.__name__))
                    description = str(getattr(agent_cls, "description", "") or "")
                    if matches(query, ref, name, description):
                        rows.append(
                            {
                                "roster_ref": ref,
                                "name": name,
                                "description": clip(description, 160),
                            }
                        )
            return {"total": len(rows), "classes": rows[:120]}

        return guarded(_FEATURE, _run)

    return [
        list_workspace_agents,
        get_workspace_agent,
        list_agent_classes,
    ]
