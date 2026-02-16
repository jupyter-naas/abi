"""
Audit Logging Service
Tracks sensitive operations for security and compliance.
"""

import json
from datetime import datetime
from uuid import uuid4

from fastapi import Request
from naas_abi.apps.nexus.apps.api.app.core.database import async_engine
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from sqlalchemy import text


async def log_audit_event(
    action: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
    request: Request | None = None,
    success: bool = True,
) -> None:
    """
    Log an audit event.

    Args:
        action: Action type ('login', 'logout', 'register', 'password_change', etc.)
        user_id: User performing the action
        resource_type: Type of resource affected ('user', 'workspace', 'conversation', etc.)
        resource_id: ID of the resource
        details: Additional context as dict (will be JSON-encoded)
        request: FastAPI Request object (for IP/user-agent extraction)
        success: Whether the action succeeded
    """
    log_id = f"audit-{uuid4().hex[:12]}"
    now = datetime.now(UTC).replace(tzinfo=None)

    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    details_json = json.dumps(details) if details else None

    try:
        async with async_engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO audit_logs
                    (id, user_id, action, resource_type, resource_id, details, ip_address, user_agent, success, created_at)
                    VALUES
                    (:id, :user_id, :action, :resource_type, :resource_id, :details, :ip_address, :user_agent, :success, :created_at)
                """),
                {
                    "id": log_id,
                    "user_id": user_id,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "details": details_json,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "success": success,
                    "created_at": now,
                },
            )
    except Exception as e:
        # Don't fail the request if audit logging fails
        print(f"Audit log failed: {e}")


async def log_login(user_id: str, success: bool, request: Request | None = None, details: dict | None = None) -> None:
    """Log a login attempt."""
    await log_audit_event("login", user_id=user_id, success=success, request=request, details=details)


async def log_logout(user_id: str, request: Request | None = None) -> None:
    """Log a logout."""
    await log_audit_event("logout", user_id=user_id, request=request)


async def log_register(user_id: str, request: Request | None = None) -> None:
    """Log a new user registration."""
    await log_audit_event("register", user_id=user_id, resource_type="user", resource_id=user_id, request=request)


async def log_password_change(user_id: str, request: Request | None = None, forced: bool = False) -> None:
    """Log a password change."""
    await log_audit_event(
        "password_change",
        user_id=user_id,
        resource_type="user",
        resource_id=user_id,
        request=request,
        details={"forced": forced}
    )


async def log_token_refresh(user_id: str, request: Request | None = None) -> None:
    """Log a token refresh."""
    await log_audit_event("token_refresh", user_id=user_id, request=request)


async def log_token_revocation(user_id: str, reason: str, request: Request | None = None) -> None:
    """Log a token revocation."""
    await log_audit_event("token_revocation", user_id=user_id, request=request, details={"reason": reason})
