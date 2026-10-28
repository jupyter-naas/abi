"""Auth FastAPI primary adapter: the signed-in user's own account.

Nexus has no login of its own. People sign in at an identity provider
(``/api/auth/oidc``, ``services/oidc``): what is here is the profile and avatar of
whoever is signed in.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.auth import avatar_store, user_drive_profile
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
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    is_safe_drive_id,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions as StorageExceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from sqlalchemy.ext.asyncio import AsyncSession

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
async def get_me(
    current_user: User = Depends(get_current_user_required),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """The signed-in account, with organization member values where it has none."""
    record = await auth_service.get_user(current_user.id)
    if record is None:
        return await with_platform_role(current_user)
    return await to_signed_in_user(await auth_service.with_account_fallbacks(record))


async def _sync_drive_profile(
    db: AsyncSession, object_storage: ObjectStorageService, user_id: str
) -> None:
    """Refresh user.json, org_member.json and .USER.md in the user's drive (best effort)."""
    await user_drive_profile.sync_user_drive_profile_safely(
        db, object_storage, user_id, datetime.now(UTC)
    )


@router.patch("/me", response_model=User)
async def update_me(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user_required),
    auth_service: AuthService = Depends(get_auth_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        user = await auth_service.update_profile(
            user_id=current_user.id,
            name=updates.name,
            organization=updates.organization,
            job_title=updates.job_title,
            bio=updates.bio,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    await _sync_drive_profile(db, object_storage, user.id)
    return await to_signed_in_user(await auth_service.with_account_fallbacks(user))


@router.post("/upload-avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    auth_service: AuthService = Depends(get_auth_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Store the picture in the user's drive (see ``avatar_store``); the old one is archived."""
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

    saved = avatar_store.save_avatar(
        object_storage, current_user.id, content, ext, datetime.now(UTC)
    )
    url = avatar_store.avatar_url(current_user.id, saved.digest)
    previous_avatar = current_user.avatar
    if url != previous_avatar:
        try:
            updated = await auth_service.update_avatar(user_id=current_user.id, avatar_url=url)
        except UserNotFoundError as exc:
            raise HTTPException(status_code=404, detail="User not found") from exc
        # A picture from before the drive layout: its file is no longer used.
        _delete_old_avatar(object_storage, previous_avatar)
        await _sync_drive_profile(db, object_storage, updated.id)

    return {"avatar_url": url, "filename": saved.key, "changed": saved.changed}


def _drive_avatar_response(
    object_storage: ObjectStorageService, user_id: str, basename: str
) -> Response:
    if not is_safe_drive_id(user_id):
        raise HTTPException(status_code=404, detail="Avatar not found")
    stored = avatar_store.read_avatar(object_storage, user_id, basename)
    if stored is None:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return Response(
        content=stored.content,
        media_type=AVATAR_MIME_TYPES.get(stored.extension, "application/octet-stream"),
        # The stored URL carries ?v=<digest>, so a new picture gets a new URL.
        headers={"Cache-Control": "private, max-age=86400"},
    )


@router.get("/avatar/user/{user_id}")
async def get_user_avatar(
    user_id: str,
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> Response:
    """The user's account picture from their drive. Public, like the legacy route:
    ``<img>`` tags cannot send a bearer token."""
    return _drive_avatar_response(object_storage, user_id, avatar_store.AVATAR_BASENAME)


@router.get("/avatar/user/{user_id}/org")
async def get_user_org_avatar(
    user_id: str,
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> Response:
    """Legacy organization member picture (``avatar_org.*``, shared by every org). Public."""
    return _drive_avatar_response(object_storage, user_id, avatar_store.ORG_AVATAR_BASENAME)


@router.get("/avatar/user/{user_id}/org/{org_id}")
async def get_user_org_avatar_for_org(
    user_id: str,
    org_id: str,
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> Response:
    """The member picture one organization set (``avatar_org_<org_id>.*``). Public."""
    if not is_safe_drive_id(org_id):
        raise HTTPException(status_code=404, detail="Avatar not found")
    return _drive_avatar_response(object_storage, user_id, avatar_store.org_avatar_basename(org_id))


@router.get("/avatar/{filename}")
async def get_avatar(
    filename: str,
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> Response:
    """Legacy pictures (and organization member pictures) under AVATAR_STORAGE_PREFIX."""
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
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Archive the current picture in the drive, then clear it."""
    previous_avatar = current_user.avatar
    try:
        updated = await auth_service.update_avatar(user_id=current_user.id, avatar_url=None)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc

    avatar_store.remove_avatar(object_storage, current_user.id, datetime.now(UTC))
    _delete_old_avatar(object_storage, previous_avatar)
    await _sync_drive_profile(db, object_storage, updated.id)

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
    if previous_avatar.startswith("/api/auth/avatar/user/"):
        # Drive pictures are archived by avatar_store, never deleted here.
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
