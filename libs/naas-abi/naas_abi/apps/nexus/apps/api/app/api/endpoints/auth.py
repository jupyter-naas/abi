"""Compatibility layer for auth exports."""

from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary import (
    ALLOWED_AVATAR_EXTENSIONS,
    AVATAR_STORAGE_PREFIX,
    MAX_AVATAR_SIZE,
    User,
    UserUpdate,
    bearer_token,
    get_avatar,
    get_current_user,
    get_current_user_required,
    get_me,
    remove_avatar,
    router,
    update_me,
    upload_avatar,
)

__all__ = [
    "ALLOWED_AVATAR_EXTENSIONS",
    "AVATAR_STORAGE_PREFIX",
    "MAX_AVATAR_SIZE",
    "User",
    "UserUpdate",
    "bearer_token",
    "get_avatar",
    "get_current_user",
    "get_current_user_required",
    "get_me",
    "remove_avatar",
    "router",
    "update_me",
    "upload_avatar",
]
