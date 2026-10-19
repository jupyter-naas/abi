"""Auth FastAPI primary adapter: the signed-in user's own account.

Nexus has no login of its own. People sign in at an identity provider
(``/api/auth/oidc``, ``services/oidc``): what is here is the profile and avatar of
whoever is signed in.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service,
    get_current_user_required,
    to_signed_in_user,
    with_platform_role,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
    UserUpdate,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    AuthService,
    UserNotFoundError,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions as StorageExceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

logger = logging.getLogger(__name__)

router = APIRouter()

AVATAR_STORAGE_PREFIX = "naas_abi/nexus/avatars"
# Avatars used to be stored at the datastore root. They are still served from
# there and moved to AVATAR_STORAGE_PREFIX on first read (see _read_avatar).
LEGACY_AVATAR_STORAGE_PREFIX = "nexus/avatars"
ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
AVATAR_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
MAX_AVATAR_SIZE = 2 * 1024 * 1024


def _get_object_storage(request: Request) -> ObjectStorageService:
    storage = getattr(request.app.state, "object_storage", None)
    if storage is not None:
        return storage
    try:
        from naas_abi import ABIModule  # noqa: PLC0415

        module = ABIModule.get_instance()
        storage = module.engine.services.object_storage
        request.app.state.object_storage = storage
        return storage
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Object storage is not initialized.",
        ) from exc


@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user_required)) -> User:
    return await with_platform_role(current_user)


@router.patch("/me", response_model=User)
async def update_me(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user_required),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    try:
        user = await auth_service.update_profile(
            user_id=current_user.id,
            name=updates.name,
            company=updates.company,
            role=updates.role,
            bio=updates.bio,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    return await to_signed_in_user(user)


@router.post("/upload-avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    auth_service: AuthService = Depends(get_auth_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_AVATAR_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 2MB)")

    unique_filename = f"{current_user.id}-{os.urandom(4).hex()}{ext}"
    object_storage.put_object(AVATAR_STORAGE_PREFIX, unique_filename, content)

    avatar_url = f"/api/auth/avatar/{unique_filename}"
    previous_avatar = current_user.avatar
    try:
        await auth_service.update_avatar(user_id=current_user.id, avatar_url=avatar_url)
    except UserNotFoundError as exc:
        try:
            object_storage.delete_object(AVATAR_STORAGE_PREFIX, unique_filename)
        except Exception:
            pass
        raise HTTPException(status_code=404, detail="User not found") from exc

    _delete_old_avatar(object_storage, previous_avatar, unique_filename)

    return {"avatar_url": avatar_url, "filename": unique_filename}


@router.get("/avatar/{filename}")
async def get_avatar(
    filename: str,
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> Response:
    ext = os.path.splitext(filename)[1].lower()
    media_type = AVATAR_MIME_TYPES.get(ext, "application/octet-stream")
    try:
        content = _read_avatar(object_storage, filename)
    except StorageExceptions.ObjectNotFound:
        raise HTTPException(status_code=404, detail="Avatar not found") from None
    return Response(content=content, media_type=media_type)


@router.delete("/avatar")
async def remove_avatar(
    current_user: User = Depends(get_current_user_required),
    auth_service: AuthService = Depends(get_auth_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> dict:
    previous_avatar = current_user.avatar
    try:
        await auth_service.update_avatar(user_id=current_user.id, avatar_url=None)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc

    _delete_old_avatar(object_storage, previous_avatar)

    return {"status": "ok"}


def _read_avatar(object_storage: ObjectStorageService, filename: str) -> bytes:
    """The avatar's bytes, moving a legacy one under AVATAR_STORAGE_PREFIX on the way.

    Raises ``ObjectNotFound`` when neither location has it.
    """
    try:
        return object_storage.get_object(AVATAR_STORAGE_PREFIX, filename)
    except StorageExceptions.ObjectNotFound:
        pass
    content = object_storage.get_object(LEGACY_AVATAR_STORAGE_PREFIX, filename)
    try:
        object_storage.put_object(AVATAR_STORAGE_PREFIX, filename, content)
        object_storage.delete_object(LEGACY_AVATAR_STORAGE_PREFIX, filename)
    except Exception as exc:  # noqa: BLE001 - the read already succeeded
        logger.warning("Could not move legacy avatar %s: %s", filename, exc)
    return content


def _delete_old_avatar(
    object_storage: ObjectStorageService,
    previous_avatar: str | None,
    exclude_filename: str | None = None,
) -> None:
    if not previous_avatar or not previous_avatar.startswith("/api/auth/avatar/"):
        return
    key = previous_avatar.rsplit("/", 1)[-1]
    if key == exclude_filename:
        return
    for prefix in (AVATAR_STORAGE_PREFIX, LEGACY_AVATAR_STORAGE_PREFIX):
        try:
            object_storage.delete_object(prefix, key)
        except Exception:
            pass


class AuthFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router
