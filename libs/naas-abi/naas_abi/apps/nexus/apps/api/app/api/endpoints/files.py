"""Backward-compatible files endpoint export."""

from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__FastAPI import (  # noqa: E501
    router,
)

__all__ = ["router"]
