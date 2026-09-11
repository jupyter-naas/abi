"""AgentCatalogAgent tools for Settings > Agents and Settings > Skills.

Reads go through the same registry services as ``/api/agents`` and
``/api/skills`` (IAM scope + workspace access), on a session bound the way
the HTTP layer binds one. ``list_agent_classes`` shows the code-registered
agents a workspace can put on its roster (``agents:`` in config.yaml, form
``"<module> <ClassName>"``). The agent or skill open on
``/settings/agents/<id>`` or ``/settings/skills/<id>`` arrives as the open
feature resource (kind ``agent`` or ``skill``).
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
SKILL_RESOURCE_KIND = "skill"
_FEATURE = "Agent Catalog"


def _registry() -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry

    return ServiceRegistry.instance()


async def _workspace_agents(db: Any, user_id: str, workspace_id: str) -> Any:
    role = await require_member(db, user_id, workspace_id)
    if isinstance(role, dict):
        return role
    with bound_session(db):
        return await _registry().agents.list_workspace_agents(
            request_context(user_id), workspace_id
        )


async def _workspace_skills(db: Any, user_id: str, workspace_id: str) -> Any:
    role = await require_member(db, user_id, workspace_id)
    if isinstance(role, dict):
        return role
    with bound_session(db):
        return await _registry().skills.list_visible_skills(
            request_context(user_id), workspace_id
        )


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
    def list_workspace_skills(query: str = "") -> Any:
        """Skills visible to you in this workspace: slug (/slug to invoke),
        name, scope (user, workspace, organization), enabled, description."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx

        async def _run(db: Any) -> Any:
            skills = await _workspace_skills(db, user_id, workspace_id)
            if isinstance(skills, dict):
                return skills
            rows = [
                {
                    "id": s.id,
                    "slug": s.slug,
                    "name": s.name,
                    "scope": s.scope,
                    "enabled": s.enabled,
                    "description": clip(s.description, 200),
                }
                for s in skills
                if matches(query, s.slug, s.name, s.description)
            ]
            return {"total": len(rows), "skills": rows}

        return guarded(_FEATURE, lambda: run_db(_run))

    @tool
    def get_workspace_skill(skill: str = "") -> Any:
        """One skill by id or slug, with its full prompt. Omit skill to use
        the one open in Settings > Skills."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        wanted = (skill or "").strip().lstrip("/") or active_feature_resource_id(
            SKILL_RESOURCE_KIND
        )
        if not wanted:
            return {"error": "No skill is open. Pass skill (id or slug)."}

        async def _run(db: Any) -> Any:
            skills = await _workspace_skills(db, user_id, workspace_id)
            if isinstance(skills, dict):
                return skills
            found = next((s for s in skills if wanted in (s.id, s.slug)), None)
            if found is None:
                return {
                    "error": f"No visible skill {wanted}. See list_workspace_skills."
                }
            out = jsonable(found)
            out["prompt"] = clip(found.prompt, 4000)
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
        list_workspace_skills,
        get_workspace_skill,
        list_agent_classes,
    ]
