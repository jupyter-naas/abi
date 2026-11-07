"""Which workspace owns each knowledge graph: IAM placements.

A graph a workspace creates is placed in it by the kernel's create rule. The
ones that already exist carry a ``graphWorkspaceId`` triple in Nexus's
application graph, written before graphs had placements: ``place_existing``
applies them at startup, and the workspaces' saved assignments are projected
into IAM in the same pass (``graph_grants``).
"""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.nexus_catalog import (
    NexusCatalogStore,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.sparql_safe import (
    sparql_string_literal,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.placements import (
    Placement,
    on_workspace_created,
    placement_source,
)
from naas_abi.apps.nexus.graph_policy_config import NEXUS_GRAPH
from naas_abi_core import logger
from naas_abi_core.services.triple_store.iam_catalog import SERVICE
from sqlalchemy.ext.asyncio import AsyncSession

OWNER_PREDICATE = "http://ontology.naas.ai/nexus/graphWorkspaceId"


def graph_placement(iri: str, workspace_id: str) -> Placement:
    return Placement(SERVICE, iri, workspace_id, kind="opaque")


def legacy_owned_graphs(store: Any, workspace_id: str) -> set[str]:
    """The graphs the application graph records as ``workspace_id``'s."""
    query = f"""
        SELECT DISTINCT ?g WHERE {{ GRAPH <{NEXUS_GRAPH}> {{
            ?g <{OWNER_PREDICATE}> {sparql_string_literal(workspace_id)} .
        }} }}
    """
    return {str(row.g) for row in NexusCatalogStore(store).query(query)}


def legacy_owners(store: Any) -> dict[str, list[str]]:
    """``{graph: [workspace, ...]}`` of the application graph's ownership triples."""
    owners: dict[str, list[str]] = {}
    for row in NexusCatalogStore(store).query(
        f"SELECT ?g ?ws WHERE {{ GRAPH <{NEXUS_GRAPH}> {{ ?g <{OWNER_PREDICATE}> ?ws }} }}"
    ):
        owners.setdefault(str(row.g), []).append(str(row.ws))
    return owners


def _store() -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService

    return GraphService()._get_catalog_store()


@placement_source
async def workspace_graph_placements(db: AsyncSession) -> list[Placement]:
    """Every graph the application graph records as a workspace's."""
    placements = []
    for iri, workspaces in sorted(legacy_owners(_store()).items()):
        if len(workspaces) > 1:
            logger.warning(
                f"Graph {iri} is recorded for {len(workspaces)} workspaces; "
                f"placed in {sorted(workspaces)[0]}"
            )
        placements.append(graph_placement(iri, sorted(workspaces)[0]))
    return placements


@placement_source
async def workspace_graph_grants(db: AsyncSession) -> list[Placement]:
    """No placement: applies the workspaces' saved graph assignments to IAM, in
    the same startup pass, so a workspace holds what it was given."""
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.graph_grants import (
        sync_all,
    )

    await sync_all(db, store=_store())
    return []


@on_workspace_created
async def new_workspace_grants(db: AsyncSession, workspace_id: str) -> list[Placement]:
    """No placement: the new workspace holds its saved (default) graph assignments."""
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.graph_grants import (
        sync_workspace,
    )

    await sync_workspace(db, workspace_id, store=_store())
    return []
