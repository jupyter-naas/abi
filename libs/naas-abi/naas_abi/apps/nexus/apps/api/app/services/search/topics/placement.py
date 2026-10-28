"""The search cache a workspace owns, placed in it.

``cache/key/search_topics_<digest>_*`` is the workspace's: the digest is
``SearchCache``'s, of fixed length, so a prefix never reaches another
workspace's keys. Placed at startup for the workspaces that exist
(``place_existing``) and the first time a workspace is searched.
"""

from __future__ import annotations

from collections.abc import Iterable

from naas_abi.apps.nexus.apps.api.app.services.iam.placements import (
    Placement,
    on_workspace_created,
    place,
    placement_source,
)
from naas_abi.apps.nexus.apps.api.app.services.search.topics.cache import workspace_prefix
from naas_abi_core import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SERVICE = "cache"

_PLACED: set[str] = set()


def search_cache_placement(workspace_id: str) -> Placement:
    return Placement(
        SERVICE, workspace_prefix(workspace_id), workspace_id, prefix=True, kind="opaque"
    )


@placement_source
async def search_caches(db: AsyncSession) -> Iterable[Placement]:
    rows = await db.execute(text("SELECT id FROM workspaces"))
    return [search_cache_placement(str(workspace_id)) for (workspace_id,) in rows]


@on_workspace_created
async def new_workspace_search_cache(db: AsyncSession, workspace_id: str) -> Iterable[Placement]:
    return [search_cache_placement(workspace_id)]


async def ensure_search_cache_placed(workspace_id: str) -> None:
    """Place the cache of a workspace the caller was just authorized in. The cache is
    best-effort: a placement that fails is logged and the search answers uncached."""
    if workspace_id in _PLACED:
        return
    try:
        await place(search_cache_placement(workspace_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Search cache of workspace {workspace_id} not placed: {exc}")
        return
    _PLACED.add(workspace_id)
