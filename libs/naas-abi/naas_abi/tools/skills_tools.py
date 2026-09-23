"""SkillsAgent tools for Nexus Skills (reusable prompts invoked with ``/slug``).

Reads and writes go through the same ``SkillService`` as ``/api/skills``
(IAM scope + workspace access), on a session bound the way the HTTP layer
binds one. Creating a skill here *saves* it: the agent is the create path,
so nothing has to be drafted into the conversation for the user to copy.

The skill open on ``/settings/skills/<id>`` arrives as the open feature
resource (kind ``skill``), so the tools default to it.
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

SKILL_RESOURCE_KIND = "skill"
# Tools that change the catalog. The web mirrors this list
# (isSkillsWriteTool) to refresh the skills store after a chat turn.
SKILL_WRITE_TOOLS = ("create_skill", "update_skill", "delete_skill")
_FEATURE = "Skills"
_MAX_PROMPT = 4000


def _registry() -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry

    return ServiceRegistry.instance()


async def _visible_skills(db: Any, user_id: str, workspace_id: str) -> Any:
    role = await require_member(db, user_id, workspace_id)
    if isinstance(role, dict):
        return role
    with bound_session(db):
        return await _registry().skills.list_visible_skills(
            request_context(user_id), workspace_id
        )


def _skill_row(skill: Any) -> dict[str, Any]:
    return {
        "id": skill.id,
        "slug": skill.slug,
        "name": skill.name,
        "scope": skill.scope,
        "enabled": skill.enabled,
        "description": clip(skill.description, 200),
    }


def _resolve(skills: list[Any], wanted: str) -> Any | None:
    needle = wanted.strip().lstrip("/").lower()
    return next(
        (s for s in skills if needle in (s.id.lower(), s.slug.lower())),
        next((s for s in skills if s.name.lower() == needle), None),
    )


def _wanted_skill(skill: str) -> str:
    """The skill the caller means: what they named, else the one open."""
    return (skill or "").strip().lstrip("/") or (
        active_feature_resource_id(SKILL_RESOURCE_KIND) or ""
    )


def skills_tools() -> list[BaseTool]:
    @tool
    def list_workspace_skills(query: str = "") -> Any:
        """Skills visible to you in this workspace: slug (/slug to invoke),
        name, scope (user, workspace, organization), enabled, description."""
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx

        async def _run(db: Any) -> Any:
            skills = await _visible_skills(db, user_id, workspace_id)
            if isinstance(skills, dict):
                return skills
            rows = [
                _skill_row(s)
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
        wanted = _wanted_skill(skill)
        if not wanted:
            return {"error": "No skill is open. Pass skill (id or slug)."}

        async def _run(db: Any) -> Any:
            skills = await _visible_skills(db, user_id, workspace_id)
            if isinstance(skills, dict):
                return skills
            found = _resolve(skills, wanted)
            if found is None:
                return {
                    "error": f"No visible skill {wanted}. See list_workspace_skills."
                }
            out = jsonable(found)
            out["prompt"] = clip(found.prompt, _MAX_PROMPT)
            return out

        return guarded(_FEATURE, lambda: run_db(_run))

    @tool
    def create_skill(
        name: str,
        prompt: str,
        slug: str = "",
        description: str = "",
        scope: str = "user",
    ) -> Any:
        """Save a new skill in this workspace. It is live right away: the user
        invokes it with /<slug>, and it joins the catalog every chat turn sees.

        name: short title. prompt: the full instructions the skill runs (goal,
        constraints, output format), written to stand on its own. slug: the
        chat command, lowercase and hyphenated, derived from the task (omit to
        slugify the name; "skills" and "create-skill" are reserved). scope:
        user (private, the default), workspace, or organization.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        if not (name or "").strip():
            return {"error": "name is required."}
        if not (prompt or "").strip():
            return {"error": "prompt is required: it is what the skill runs."}

        async def _run(db: Any) -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.skills import (
                SkillCreateInput,
            )
            from naas_abi.apps.nexus.apps.api.app.services.skills.service import (
                normalize_slug,
            )

            role = await require_member(db, user_id, workspace_id)
            if isinstance(role, dict):
                return role
            with bound_session(db):
                created = await _registry().skills.create_skill(
                    request_context(user_id),
                    SkillCreateInput(
                        workspace_id=workspace_id,
                        user_id=user_id,
                        name=name.strip(),
                        slug=(slug or "").strip() or normalize_slug(name),
                        prompt=prompt.strip(),
                        description=(description or "").strip() or None,
                        scope=(scope or "user").strip() or "user",
                    ),
                )
            out = _skill_row(created)
            out["saved"] = True
            out["command"] = f"/{created.slug}"
            return out

        return guarded(_FEATURE, lambda: run_db(_run))

    @tool
    def update_skill(
        skill: str = "",
        name: str = "",
        slug: str = "",
        description: str = "",
        prompt: str = "",
        scope: str = "",
        enabled: bool | None = None,
    ) -> Any:
        """Change a saved skill. Omit skill to use the one open in Settings >
        Skills. Only the fields you pass change; pass enabled to turn the
        skill on or off. A user-scoped skill can only be changed by its
        creator.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        wanted = _wanted_skill(skill)
        if not wanted:
            return {"error": "No skill is open. Pass skill (id or slug)."}
        fields = {
            "name": (name or "").strip() or None,
            "slug": (slug or "").strip() or None,
            "description": (description or "").strip() or None,
            "prompt": (prompt or "").strip() or None,
            "scope": (scope or "").strip() or None,
            "enabled": enabled,
        }
        if all(value is None for value in fields.values()):
            return {"error": "Nothing to change. Pass at least one field."}

        async def _run(db: Any) -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.skills import (
                SkillUpdateInput,
            )

            skills = await _visible_skills(db, user_id, workspace_id)
            if isinstance(skills, dict):
                return skills
            found = _resolve(skills, wanted)
            if found is None:
                return {
                    "error": f"No visible skill {wanted}. See list_workspace_skills."
                }
            with bound_session(db):
                updated = await _registry().skills.update_skill(
                    request_context(user_id),
                    found.id,
                    SkillUpdateInput(**fields),
                )
            if updated is None:
                return {"error": f"Skill {found.slug} no longer exists."}
            out = _skill_row(updated)
            out["updated"] = sorted(k for k, v in fields.items() if v is not None)
            out["command"] = f"/{updated.slug}"
            return out

        return guarded(_FEATURE, lambda: run_db(_run))

    @tool
    def delete_skill(skill: str = "") -> Any:
        """Delete a saved skill for good. Only call it when the user asked for
        that skill to be deleted. Omit skill to use the one open in Settings >
        Skills. A user-scoped skill can only be deleted by its creator.
        """
        ctx = tool_context()
        if isinstance(ctx, dict):
            return ctx
        user_id, workspace_id = ctx
        wanted = _wanted_skill(skill)
        if not wanted:
            return {"error": "No skill is open. Pass skill (id or slug)."}

        async def _run(db: Any) -> Any:
            skills = await _visible_skills(db, user_id, workspace_id)
            if isinstance(skills, dict):
                return skills
            found = _resolve(skills, wanted)
            if found is None:
                return {
                    "error": f"No visible skill {wanted}. See list_workspace_skills."
                }
            with bound_session(db):
                deleted = await _registry().skills.delete_skill(
                    request_context(user_id), found.id
                )
            if not deleted:
                return {"error": f"Skill {found.slug} could not be deleted."}
            return {"deleted": True, "slug": found.slug, "name": found.name}

        return guarded(_FEATURE, lambda: run_db(_run))

    return [
        list_workspace_skills,
        get_workspace_skill,
        create_skill,
        update_skill,
        delete_skill,
    ]
