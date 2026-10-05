"""Skills FastAPI primary adapter."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
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
    return RequestContext(
        token_data=TokenData(user_id=current_user.id, scopes={"*"}, is_authenticated=True)
    )


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


class SkillPackageFileBody(BaseModel):
    path: str = Field(..., min_length=1, max_length=400)
    body: str = ""


class SkillPackageBody(BaseModel):
    """A skill package the user asked to write. Not an agent tool."""

    workspace_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    when_to_use: str = Field(..., min_length=1, max_length=2000)
    body: str = Field(..., min_length=1)
    slug: str | None = Field(default=None, max_length=100)
    files: list[SkillPackageFileBody] = Field(default_factory=list)


class SkillUpdateBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    prompt: str | None = Field(default=None, min_length=1)
    scope: str | None = None
    enabled: bool | None = None


@router.get("/")
async def list_skills(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> list[SkillRecord]:
    await require_workspace_access(current_user.id, workspace_id)
    return await skill_service.list_visible_skills(
        context=request_context(current_user),
        workspace_id=workspace_id,
    )


@router.post("/")
async def create_skill(
    body: SkillCreateBody,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> SkillRecord:
    await require_workspace_access(current_user.id, body.workspace_id)
    try:
        return await skill_service.create_skill(
            context=request_context(current_user),
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


@router.post("/package")
async def write_skill_package(
    body: SkillPackageBody,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> dict[str, object]:
    """Write SKILL.md when the user asks. Prompt rows stay on POST /api/skills/."""
    await require_workspace_access(current_user.id, body.workspace_id)
    try:
        path = skill_service.write_requested_skill_package(
            body.workspace_id,
            slug=body.slug or normalize_slug(body.name),
            name=body.name,
            description=body.description,
            when_to_use=body.when_to_use,
            body=body.body,
            files=[{"path": item.path, "body": item.body} for item in body.files],
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "slug": path.parent.name,
        "file": "SKILL.md",
        "files": ["SKILL.md", *[item.path for item in body.files]],
    }


@router.get("/{skill_id}/files/{file_path:path}")
async def read_skill_file(
    skill_id: str,
    file_path: str,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> dict[str, str]:
    try:
        skill = await skill_service.get_skill(
            context=request_context(current_user),
            skill_id=skill_id,
        )
    except SkillPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if not skill.builtin:
        await require_workspace_access(current_user.id, skill.workspace_id)
    content = skill_service.read_skill_package_file(skill, file_path)
    if content is None:
        raise HTTPException(status_code=404, detail="Skill file not found")
    return {"path": file_path, "content": content}


@router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> SkillRecord:
    try:
        skill = await skill_service.get_skill(
            context=request_context(current_user),
            skill_id=skill_id,
        )
    except SkillPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if not skill.builtin:
        await require_workspace_access(current_user.id, skill.workspace_id)
    return skill


@router.patch("/{skill_id}")
async def update_skill(
    skill_id: str,
    body: SkillUpdateBody,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> SkillRecord:
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


@router.post("/{skill_id}/use")
async def mark_skill_used(
    skill_id: str,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> SkillRecord:
    skill = await skill_service.mark_skill_used(
        context=request_context(current_user),
        skill_id=skill_id,
        now=_now(),
    )
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user_required),
    skill_service: SkillService = Depends(get_skill_service),
) -> dict[str, str]:
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
