"""Resolve workspace configuration and persisted ownership for each request."""

from __future__ import annotations

import asyncio
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.access import (
    OWNER_PREDICATE,
    GraphAccessScope,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.sparql_safe import (
    sparql_string_literal,
)
from naas_abi.apps.nexus.graph_policy_config import (
    NEXUS_GRAPH,
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


def owned_graphs(store: Any, workspace_id: str) -> set[str]:
    # Ownership is server-written metadata, not inferred from a graph label,
    # namespace, ontology visibility, or its creator's other memberships.
    query = f"""
        SELECT DISTINCT ?g WHERE {{ GRAPH <{NEXUS_GRAPH}> {{
            ?g <{OWNER_PREDICATE}> {sparql_string_literal(workspace_id)} .
        }} }}
    """
    return {str(row.g) for row in store.query(query)}


def catalog_graphs(store: Any) -> set[str]:
    """Include stored graphs and registered empty graphs; exclude application metadata."""
    graphs = {str(uri) for uri in store.list_graphs()}
    for row in store.query(
        f"SELECT DISTINCT ?g WHERE {{ GRAPH <{NEXUS_GRAPH}> {{ "
        f"?g a <{KnowledgeGraph._class_uri}> . FILTER(isIRI(?g)) }} }}"
    ):
        graphs.add(str(row.g))
    return graphs - {NEXUS_GRAPH}


async def load_workspace_scope(
    db: AsyncSession,
    store: Any,
    workspace_id: str,
    role: str,
) -> GraphAccessScope:
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.resource_access_postgres import (
        load_resource_policy,
    )

    saved = await load_resource_policy(db, workspace_id, "graphs")
    config = WorkspaceGraphPolicyConfig.model_validate(saved.data)
    owned = (
        await asyncio.to_thread(owned_graphs, store, workspace_id)
        if config.include_owned
        else set()
    )
    catalog = (
        await asyncio.to_thread(catalog_graphs, store) if config.read_all else set()
    )
    return GraphAccessScope.resolve(workspace_id, config, owned, role, catalog=catalog)


def catalog_inventory(
    store: Any,
    settings: Any,
    policies: dict[str, WorkspaceGraphPolicyConfig] | None = None,
) -> list[dict[str, object]]:
    """Metadata only; caller must be a platform administrator, not a workspace member."""
    graphs = catalog_graphs(store)
    owners: dict[str, list[str]] = {}
    for row in store.query(
        f"SELECT ?g ?ws WHERE {{ GRAPH <{NEXUS_GRAPH}> {{ ?g <{OWNER_PREDICATE}> ?ws }} }}"
    ):
        owners.setdefault(str(row.g), []).append(str(row.ws))
    grants: dict[str, list[dict[str, str]]] = {}
    if policies is None:
        policies = {
            f"{org.slug}/{ws.slug}": config_for_workspace(settings, org.slug, ws.slug)
            for org in getattr(settings, "organizations", None) or []
            for ws in getattr(org, "workspaces", None) or []
        }
    for workspace, policy in policies.items():
        readable = (
            (graphs if policy.read_all else set())
            | set(policy.read)
            | set(policy.write)
        )
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
