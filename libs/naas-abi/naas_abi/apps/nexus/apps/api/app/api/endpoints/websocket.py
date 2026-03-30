"""Backward-compatible websocket endpoint export."""

from naas_abi.apps.nexus.apps.api.app.services.websocket.handlers import router

__all__ = ["router"]
