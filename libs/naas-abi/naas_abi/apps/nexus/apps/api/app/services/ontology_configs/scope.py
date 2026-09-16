"""Build the per-workspace enablement scope for the ontology catalog.

Shared by the ontology adapter (which uses it to filter every catalog and
graph route) and the ontology-configs adapter (which uses it to render the
Settings table). Kept out of both primary adapters so neither has to
import the other.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
    OntologyCatalogScope,
    workspace_seed_for_slug,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology_configs.service import (
    OntologyConfigsService,
)
from sqlalchemy import select


async def workspace_slug(workspace_id: str) -> str | None:
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.models import WorkspaceModel

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkspaceModel.slug).where(WorkspaceModel.id == workspace_id)
        )
        return result.scalar_one_or_none()


async def build_ontology_catalog_scope(
    workspace_id: str,
    configs_service: OntologyConfigsService,
) -> OntologyCatalogScope:
    """Stored rows for this workspace, plus its YAML seed list as fallback.

    Callers must have already authorized ``workspace_id`` for the user.
    """
    enabled_by_id = await configs_service.get_enabled_states(workspace_id)

    seed = workspace_seed_for_slug(await workspace_slug(workspace_id))
    seed_refs = getattr(seed, "ontologies", None) if seed is not None else None

    return OntologyCatalogScope(
        enabled_by_id=enabled_by_id,
        seed_refs=tuple(seed_refs) if seed_refs else None,
    )
