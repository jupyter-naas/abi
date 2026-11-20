from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.primary import router
from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.primary.analytics__primary_adapter__scoped import (  # noqa: E501
    organization_router,
    workspace_router,
)

__all__ = ["organization_router", "router", "workspace_router"]
