"""Gatekeeper FastAPI primary adapter."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.gatekeeper.port import (
    GatekeeperGrantCreateInput,
    GatekeeperGrantRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.gatekeeper.service import (
    GatekeeperNexusService,
    GatekeeperUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
from naas_abi.apps.nexus.apps.api.app.services.registry import (
    ServiceRegistry,
    get_service_registry,
)
from pydantic import BaseModel, Field

router = APIRouter(dependencies=[Depends(get_current_user_required)])


class GatekeeperFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


def get_gatekeeper_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> GatekeeperNexusService:
    return registry.gatekeeper


def request_context(current_user: User) -> RequestContext:
    return RequestContext(
        token_data=TokenData(user_id=current_user.id, scopes={"*"}, is_authenticated=True)
    )


class GatekeeperGrantBody(BaseModel):
    resource_type: str = Field(..., min_length=1, max_length=200)
    resource_id: str = Field(..., min_length=1, max_length=500)
    actions: list[str] = Field(..., min_length=1)


class GatekeeperGrantResponse(BaseModel):
    chat_id: str
    resource_type: str
    resource_id: str
    actions: list[str]
    granted_at: datetime


def _to_response(record: GatekeeperGrantRecord) -> GatekeeperGrantResponse:
    return GatekeeperGrantResponse(
        chat_id=record.chat_id,
        resource_type=record.resource_type,
        resource_id=record.resource_id,
        actions=list(record.actions),
        granted_at=record.granted_at,
    )


@router.get("/conversations/{conversation_id}/grants")
async def list_conversation_grants(
    conversation_id: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    gatekeeper_service: GatekeeperNexusService = Depends(get_gatekeeper_service),
) -> list[GatekeeperGrantResponse]:
    try:
        grants = await gatekeeper_service.list_grants(
            context=request_context(current_user),
            workspace_id=workspace_id,
            conversation_id=conversation_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GatekeeperUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [_to_response(grant) for grant in grants]


@router.post("/conversations/{conversation_id}/grants")
async def create_conversation_grant(
    conversation_id: str,
    workspace_id: str,
    body: GatekeeperGrantBody,
    current_user: User = Depends(get_current_user_required),
    gatekeeper_service: GatekeeperNexusService = Depends(get_gatekeeper_service),
) -> GatekeeperGrantResponse:
    try:
        grant = await gatekeeper_service.grant_resource(
            context=request_context(current_user),
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            data=GatekeeperGrantCreateInput(
                resource_type=body.resource_type,
                resource_id=body.resource_id,
                actions=tuple(body.actions),
            ),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GatekeeperUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _to_response(grant)
