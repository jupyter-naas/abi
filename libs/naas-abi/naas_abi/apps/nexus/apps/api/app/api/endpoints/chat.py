"""Backward-compatible chat endpoint export.

Chat FastAPI primary adapter now lives under the chat domain package.
"""

from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__FastAPI import (  # noqa: E501
    router,
)

__all__ = ["router"]
