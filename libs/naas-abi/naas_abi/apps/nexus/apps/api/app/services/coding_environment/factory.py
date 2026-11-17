"""Which ``CodingEnvironmentStorePort`` the routes and jobs use.

Routes depend on ``get_coding_environment_store`` (the SQL store on the
request's session, so a test overriding ``get_db`` still reaches it; a test can
override this dependency itself with ``MemoryCodingEnvironmentStore``). Work
outside a request opens its own with ``open_coding_environment_store``.
Callers still handed a database session (the placement sources, chat streaming)
pass it through ``coding_environment_store``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.core import database
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.adapters.secondary.sql import (
    SqlCodingEnvironmentStore,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.port import (
    CodingEnvironmentStorePort,
)

# A store, or a database session to build the SQL store on (None: no store).
CodingEnvironmentStoreSource = Any


def coding_environment_store(
    source: CodingEnvironmentStoreSource,
) -> CodingEnvironmentStorePort | None:
    """``source`` itself when it is a store, the SQL store on it when it is a
    session, None for None."""
    if source is None:
        return None
    if isinstance(source, CodingEnvironmentStorePort):
        return source
    return SqlCodingEnvironmentStore(source)


async def get_coding_environment_store(
    db: Any = Depends(get_db),
) -> CodingEnvironmentStorePort | None:
    """The request's store (None when the request has no database)."""
    return coding_environment_store(db)


async def require_coding_environment_store(
    store: CodingEnvironmentStorePort | None = Depends(get_coding_environment_store),
) -> CodingEnvironmentStorePort:
    if store is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    return store


@asynccontextmanager
async def open_coding_environment_store() -> AsyncIterator[CodingEnvironmentStorePort]:
    """A store on a session of its own, closed on exit."""
    # Read when called: the session factory of the database in use.
    async with database.AsyncSessionLocal() as db:
        yield SqlCodingEnvironmentStore(db)
