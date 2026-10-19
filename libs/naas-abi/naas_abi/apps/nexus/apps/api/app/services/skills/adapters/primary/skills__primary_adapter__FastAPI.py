"""Skills FastAPI primary adapter."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from naas_abi.apps.nexus.apps.api.app.services.registry import (
    ServiceRegistry,
    get_service_registry,
)
from naas_abi.apps.nexus.apps.api.app.services.skills import (
    SkillCreateInput,
    SkillRecord,
    SkillService,
    SkillUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.skills.service import (
    RequestContext,
    SkillPermissionError,
    SkillValidationError,
    normalize_slug,
)
from pydantic import BaseModel, Field

router = APIRouter(dependencies=[Depends(get_current_user_required)])


class SkillsFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


def get_skill_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> SkillService:
    return registry.skills


def request_context(current_user: User) -> RequestContext:
    """Names the caller for the service (user-scoped skills are private to their
    creator); what the caller may do is IAM's, decided by the route."""
    return RequestContext(actor_user_id=current_user.id)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SkillCreateBody(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    prompt: str = Field(..., min_length=1)
    slug: str | None = Field(default=None, max_length=100)  # Defaults to slugified name
    description: str | None = Field(default=None, max_length=2000)
    scope: str = Field(default="user")  # user | workspace | organization
    enabled: bool = True


class SkillUpdateBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    prompt: str | None = Field(default=None, min_length=1)
    scope: str | None = None
    enabled: bool | None = None


@router.get("/", dependencies=[guard("ListSkills", literal="-")])
async def list_skills(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> list[SkillRecord]:
    return await skill_service.list_visible_skills(
        context=request_context(current_user),
        workspace_id=workspace_id,
    )


@router.post("/", dependencies=[declares("CreateSkill")])
async def create_skill(
    body: SkillCreateBody,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> SkillRecord:
    await authz.require("CreateSkill", user=current_user, workspace=body.workspace_id, id="-")
    try:
        return await skill_service.create_skill(
            data=SkillCreateInput(
                workspace_id=body.workspace_id,
                user_id=current_user.id,
                name=body.name,
                slug=body.slug or normalize_slug(body.name),
                prompt=body.prompt,
                description=body.description,
                scope=body.scope,
                enabled=body.enabled,
            ),
        )
    except SkillValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _load_skill(
    skill_service: SkillService, current_user: User, action: str, skill_id: str
) -> SkillRecord:
    """The skill, once the caller may perform ``action`` on it in its workspace."""
    try:
        skill = await skill_service.get_skill(
            context=request_context(current_user),
            skill_id=skill_id,
        )
    except SkillPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    await authz.require(action, user=current_user, workspace=skill.workspace_id, id=skill.id)
    return skill


@router.get("/{skill_id}", dependencies=[declares("GetSkill")])
async def get_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> SkillRecord:
    return await _load_skill(skill_service, current_user, "GetSkill", skill_id)


@router.patch("/{skill_id}", dependencies=[declares("UpdateSkill")])
async def update_skill(
    skill_id: str,
    body: SkillUpdateBody,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> SkillRecord:
    await _load_skill(skill_service, current_user, "UpdateSkill", skill_id)
    try:
        skill = await skill_service.update_skill(
            context=request_context(current_user),
            skill_id=skill_id,
            updates=SkillUpdateInput(
                name=body.name,
                slug=body.slug,
                description=body.description,
                prompt=body.prompt,
                scope=body.scope,
                enabled=body.enabled,
            ),
        )
    except SkillPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SkillValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.post("/{skill_id}/use", dependencies=[declares("MarkSkillUsed")])
async def mark_skill_used(
    skill_id: str,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> SkillRecord:
    await _load_skill(skill_service, current_user, "MarkSkillUsed", skill_id)
    skill = await skill_service.mark_skill_used(
        context=request_context(current_user),
        skill_id=skill_id,
        now=_now(),
    )
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.delete("/{skill_id}", dependencies=[declares("DeleteSkill")])
async def delete_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> dict[str, str]:
    await _load_skill(skill_service, current_user, "DeleteSkill", skill_id)
    try:
        deleted = await skill_service.delete_skill(
            context=request_context(current_user),
            skill_id=skill_id,
        )
    except SkillPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"status": "deleted"}
