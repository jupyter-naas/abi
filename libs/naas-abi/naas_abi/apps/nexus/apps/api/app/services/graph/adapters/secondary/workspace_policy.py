"""A workspace's view of the knowledge graphs, for each request.

Graph rights are IAM's (``graph_grants``, ``graph_placements``). This module
resolves which graphs a workspace offers its members: its own (IAM placed them
in it), the ones its saved assignments share with it, and, when it reads the
whole catalog, every graph of the catalog; each narrowed to what the kernel
lets the signed-in user read and write.
"""

from __future__ import annotations

import asyncio
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary import graph_iam
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.nexus_catalog import (
    NexusCatalogStore,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.graph_policy_config import (
    NEXUS_GRAPH,
    SCHEMA_GRAPH,
    WorkspaceGraphPolicyConfig,
)
from naas_abi.ontologies.modules.NexusPlatformOntology import KnowledgeGraph
from sqlalchemy.ext.asyncio import AsyncSession


def config_for_workspace(
    settings: Any, organization_slug: str, workspace_slug: str
) -> WorkspaceGraphPolicyConfig:
    # Match BOTH identities; equal workspace slugs in different organizations
    # must not accidentally inherit the first organization's grants.
    matches = [
        ws
        for org in (getattr(settings, "organizations", None) or [])
        if org.slug == organization_slug
        for ws in (getattr(org, "workspaces", None) or [])
        if ws.slug == workspace_slug
    ]
    if len(matches) > 1:
        raise GraphAccessError("Ambiguous workspace graph configuration")
    if not matches:
        return WorkspaceGraphPolicyConfig()
    return WorkspaceGraphPolicyConfig.model_validate(
        getattr(matches[0], "graphs", WorkspaceGraphPolicyConfig()).model_dump()
    )


def catalog_graphs(store: Any) -> set[str]:
    """Include stored graphs and registered empty graphs; exclude application metadata.

    Read as Nexus: it is the whole catalog, whoever asks for it."""
    catalog = NexusCatalogStore(store)
    graphs = {str(uri) for uri in catalog.list_graphs()}
    for row in catalog.query(
        f"SELECT DISTINCT ?g WHERE {{ GRAPH <{NEXUS_GRAPH}> {{ "
        f"?g a <{KnowledgeGraph._class_uri}> . FILTER(isIRI(?g)) }} }}"
    ):
        graphs.add(str(row.g))
    return graphs - {NEXUS_GRAPH}


def build_scope(
    workspace_id: str,
    config: WorkspaceGraphPolicyConfig,
    *,
    user: Any,
    owned: set[str],
    catalog: set[str],
    container: str | None,
) -> GraphAccessScope:
    """The workspace's view for ``user``: what it offers, narrowed to what IAM
    lets the user read, and to write."""
    owned = owned if config.include_owned else set()
    offered = (catalog if config.read_all else set()) | set(config.read) | set(config.write) | owned
    offered -= {NEXUS_GRAPH}
    readable = graph_iam.allowed("Query", offered, user=user)
    # The schema graph is read-only whatever IAM would say; sharing never writes it.
    writing = ((set(config.write) | owned) - {NEXUS_GRAPH, SCHEMA_GRAPH}) & readable
    writable = graph_iam.allowed("Insert", writing, user=user)
    can_create = container is not None and graph_iam.may_create(container, user=user)
    return GraphAccessScope(workspace_id, frozenset(readable), frozenset(writable), can_create)


async def load_workspace_scope(
    db: AsyncSession,
    store: Any,
    workspace_id: str,
    user: Any,
) -> GraphAccessScope:
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.resource_access_postgres import (
        load_resource_policy,
    )

    saved = await load_resource_policy(db, workspace_id, "graphs")
    config = WorkspaceGraphPolicyConfig.model_validate(saved.data)
    container = await AUTHZ.container_of(workspace_id)

    def resolve() -> GraphAccessScope:
        owned = graph_iam.owned_by(workspace_id)
        catalog = catalog_graphs(store) if config.read_all else set()
        return build_scope(
            workspace_id, config, user=user, owned=owned, catalog=catalog, container=container
        )

    return await asyncio.to_thread(resolve)


def catalog_inventory(
    store: Any,
    settings: Any,
    policies: dict[str, WorkspaceGraphPolicyConfig] | None = None,
) -> list[dict[str, object]]:
    """Metadata only; caller must be a platform administrator, not a workspace member."""
    graphs = catalog_graphs(store)
    owners: dict[str, list[str]] = {}
    for uri, workspace in graph_iam.owners().items():
        owners.setdefault(uri, []).append(workspace)
    grants: dict[str, list[dict[str, str]]] = {}
    if policies is None:
        policies = {
            f"{org.slug}/{ws.slug}": config_for_workspace(settings, org.slug, ws.slug)
            for org in getattr(settings, "organizations", None) or []
            for ws in getattr(org, "workspaces", None) or []
        }
    for workspace, policy in policies.items():
        readable = (graphs if policy.read_all else set()) | set(policy.read) | set(policy.write)
        for uri in readable:
            grants.setdefault(uri, []).append(
                {
                    "workspace": workspace,
                    "access": "write" if uri in policy.write else "read",
                }
            )
    return [
        {
            "uri": str(uri),
            "owner_workspace_ids": sorted(owners.get(str(uri), [])),
            "grants": grants.get(str(uri), []),
            "unassigned": not owners.get(str(uri)) and not grants.get(str(uri)),
        }
        for uri in sorted(graphs)
    ]
