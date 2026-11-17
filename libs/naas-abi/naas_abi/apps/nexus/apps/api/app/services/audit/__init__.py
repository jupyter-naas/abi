"""
Audit Logging Service
Tracks sensitive operations for security and compliance.
"""

import logging
from datetime import datetime
from uuid import uuid4

from fastapi import Request
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.audit.adapters.secondary.sql import SqlAuditLog
from naas_abi.apps.nexus.apps.api.app.services.audit.port import AuditEvent, AuditLogPort

logger = logging.getLogger(__name__)

_log: AuditLogPort = SqlAuditLog()


def configure_log(log: AuditLogPort) -> AuditLogPort:
    """Write every audit event to ``log`` from now on; returns the one it replaces."""
    global _log
    previous, _log = _log, log
    return previous


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
    Log an audit event. A failure to write it never fails the request.

    Args:
        action: Action type ('login', 'logout', 'token_revocation', etc.)
        user_id: User performing the action
        resource_type: Type of resource affected ('user', 'workspace', 'conversation', etc.)
        resource_id: ID of the resource
        details: Additional context as dict (will be JSON-encoded)
        request: FastAPI Request object (for IP/user-agent extraction)
        success: Whether the action succeeded
    """
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    event = AuditEvent(
        id=f"audit-{uuid4().hex[:12]}",
        action=action,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or None,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
    )
    try:
        await _log.append(event)
    except Exception:
        # Don't fail the request if audit logging fails
        logger.warning("Audit log failed for %s", action, exc_info=True)


async def log_login(
    user_id: str | None, success: bool, request: Request | None = None, details: dict | None = None
) -> None:
    """Log a login attempt."""
    await log_audit_event(
        "login", user_id=user_id, success=success, request=request, details=details
    )


async def log_logout(user_id: str, request: Request | None = None) -> None:
    """Log a logout."""
    await log_audit_event("logout", user_id=user_id, request=request)


async def log_token_revocation(user_id: str, reason: str, request: Request | None = None) -> None:
    """Log a token revocation."""
    await log_audit_event(
        "token_revocation", user_id=user_id, request=request, details={"reason": reason}
    )
