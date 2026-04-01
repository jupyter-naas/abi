"""Backward-compatible organizations endpoint export."""

from naas_abi.apps.nexus.apps.api.app.services.organizations.handlers import (
    public_router,
    router,
)

__all__ = ["router", "public_router"]
