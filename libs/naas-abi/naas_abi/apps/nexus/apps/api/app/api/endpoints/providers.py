"""Backward-compatible providers endpoint export."""

from naas_abi.apps.nexus.apps.api.app.services.providers.handlers import router

__all__ = ["router"]
