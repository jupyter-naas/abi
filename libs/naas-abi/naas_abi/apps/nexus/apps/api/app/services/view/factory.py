"""The graph view store a request uses (a FastAPI dependency tests can override)."""

from __future__ import annotations

from fastapi import Depends
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.view.adapters.secondary.sql import (
    SqlGraphViewStore,
)
from naas_abi.apps.nexus.apps.api.app.services.view.port import GraphViewStorePort
from sqlalchemy.ext.asyncio import AsyncSession


def get_graph_view_store(db: AsyncSession = Depends(get_db)) -> GraphViewStorePort:
    return SqlGraphViewStore(db)
