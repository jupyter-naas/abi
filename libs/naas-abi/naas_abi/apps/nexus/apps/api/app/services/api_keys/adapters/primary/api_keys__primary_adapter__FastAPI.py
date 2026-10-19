"""``/api/iam/api-keys`` and ``/api/iam/token``.

Key management is session-only: the route prefix ``/api/iam/`` takes no API key
(``credentials.accepted_kinds``), so a key can neither make another key nor
widen itself. ``POST /api/iam/token`` is the OAuth2 token endpoint of scripts:
``grant_type=client_credentials`` with the personal key as ``client_secret``,
form-encoded or JSON; it takes no credential but the key.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.api_keys.service import (
    MAX_DAYS,
    ApiKey,
    ApiKeyService,
    ApiKeysUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares
from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
    ensure_under_limit,
    get_rate_limit_identifier,
    record_attempt,
)
from naas_abi_core import logger
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    KeyRefusedError,
    PermissionDeniedError,
)
from pydantic import BaseModel, Field

router = APIRouter()
_service = ApiKeyService()
# The rate limit's name for failed exchanges at the token endpoint.
TOKEN_ENDPOINT = "iam_token"


def get_api_key_service() -> ApiKeyService:
    return _service


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: datetime | None
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    status: Literal["active", "revoked", "expired"]
    access: Literal["full", "read", "custom"]
    scope: list[dict[str, Any]] | None = None

    @classmethod
    def of(cls, key: ApiKey) -> ApiKeyResponse:
        return cls(
            id=key.id,
            name=key.name,
            prefix=key.prefix,
            created_at=key.created_at,
            expires_at=key.expires_at,
            last_used_at=key.last_used_at,
            revoked_at=key.revoked_at,
            status=key.status,
            access=key.access,
            scope=list(key.scope) if key.scope is not None else None,
        )


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    expires_in_days: int = Field(default=MAX_DAYS, ge=1, le=MAX_DAYS)
    access: Literal["full", "read", "custom"] = "full"
    scope: list[dict[str, Any]] | None = Field(
        default=None,
        description="Allow statements, for access=custom: the actions and resources "
        "the key is limited to (the token's abi_scope).",
    )


class ApiKeyCreated(BaseModel):
    key: ApiKeyResponse
    secret: str = Field(description="The key itself. Shown this once: it is not stored.")


def _unavailable(exc: ApiKeysUnavailable) -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


# Personal keys are the user's own (``builtin.self``: iam:key/<user>/*): the engine's IAM
# decides in the service, as the user, and the key's own narrowing never widens.
@router.get(
    "/api-keys",
    response_model=list[ApiKeyResponse],
    dependencies=[declares("iam:ListKeys")],
)
async def list_api_keys(
    current_user: User = Depends(get_current_user_required),
    service: ApiKeyService = Depends(get_api_key_service),
) -> list[ApiKeyResponse]:
    try:
        keys = await run_in_threadpool(service.list_keys, current_user.id)
    except ApiKeysUnavailable as exc:
        raise _unavailable(exc) from exc
    return [ApiKeyResponse.of(k) for k in keys]


@router.post(
    "/api-keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=[declares("iam:CreateKey")],
)
async def create_api_key(
    body: ApiKeyCreate,
    current_user: User = Depends(get_current_user_required),
    service: ApiKeyService = Depends(get_api_key_service),
) -> ApiKeyCreated:
    try:
        created = await run_in_threadpool(
            lambda: service.create_key(
                current_user.id,
                name=body.name,
                expires_in_days=body.expires_in_days,
                access=body.access,
                scope=body.scope,
            )
        )
    except ApiKeysUnavailable as exc:
        raise _unavailable(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except IAMConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return ApiKeyCreated(key=ApiKeyResponse.of(created.key), secret=created.secret)


@router.delete(
    "/api-keys/{key_id}",
    response_model=ApiKeyResponse,
    dependencies=[declares("iam:RevokeKey")],
)
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user_required),
    service: ApiKeyService = Depends(get_api_key_service),
) -> ApiKeyResponse:
    try:
        revoked = await run_in_threadpool(service.revoke_key, current_user.id, key_id)
    except ApiKeysUnavailable as exc:
        raise _unavailable(exc) from exc
    except (IAMNotFoundError, PermissionDeniedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        ) from exc
    return ApiKeyResponse.of(revoked)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int


async def _token_request(request: Request) -> dict[str, str]:
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    try:
        if content_type == "application/json":
            data = await request.json()
        else:
            data = dict(await request.form())
    except Exception as exc:  # noqa: BLE001 - a malformed body is a bad request
        raise HTTPException(status_code=400, detail="invalid_request") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="invalid_request")
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


@router.post("/token", response_model=TokenResponse)
async def token(
    request: Request,
    service: ApiKeyService = Depends(get_api_key_service),
) -> TokenResponse:
    """The OAuth2 token endpoint for scripts: a personal API key
    (``client_secret``) for a short-lived access token (``grant_type=
    client_credentials``). Every refusal says the same thing."""
    fields = await _token_request(request)
    if fields.get("grant_type") != "client_credentials":
        raise HTTPException(status_code=400, detail="unsupported_grant_type")
    secret = fields.get("client_secret", "")
    if not secret:
        raise HTTPException(status_code=400, detail="invalid_request")
    # Failed exchanges count against the caller's address, as sign-in does.
    caller = get_rate_limit_identifier(request)
    await ensure_under_limit(caller, TOKEN_ENDPOINT, settings.rate_limit_ip_attempts)
    try:
        issued = await run_in_threadpool(service.exchange, secret)
    except ApiKeysUnavailable as exc:
        raise _unavailable(exc) from exc
    except (KeyRefusedError, PermissionDeniedError):
        await record_attempt(caller, TOKEN_ENDPOINT)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except Exception:  # noqa: BLE001 - never echo what a key exchange failed on
        logger.exception("API key exchange failed")
        raise HTTPException(status_code=500, detail="server_error") from None
    return TokenResponse(
        access_token=issued.token, expires_in=max(1, int(issued.expires_at - time.time()))
    )
