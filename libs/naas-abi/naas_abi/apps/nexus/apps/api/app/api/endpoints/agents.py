"""Backward-compatible agents endpoint export."""

from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (  # noqa: E501
    router,
)

__all__ = ["router"]
