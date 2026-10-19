"""Admin assignment editor. Saved graph assignments are applied to IAM, which
the graph APIs (through the kernel) enforce; ontology assignments are read by
the ontology APIs."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
    normalize_ontology_ref,
    ontology_matches_seed,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary import graph_iam
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.graph_grants import (
    sync_workspace,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.nexus_catalog import (
    NexusCatalogStore,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
    catalog_graphs,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ as authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import guard
from naas_abi.apps.nexus.apps.api.app.services.registry import (
    ServiceRegistry,
    get_service_registry,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.resource_access_postgres import (
    ResourcePolicyPostgres,
    load_resource_policy,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.resource_access import (
    PolicyConflictError,
    ResourceAccessService,
    validate_policy,
)
from naas_abi.apps.nexus.graph_policy_config import NEXUS_GRAPH, SCHEMA_GRAPH
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def get_graph_service(registry: ServiceRegistry = Depends(get_service_registry)):
    return registry.graph


def get_ontology_service(registry: ServiceRegistry = Depends(get_service_registry)):
    return registry.ontology


Kind = Literal["ontologies", "graphs"]


class AssignmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    policy: dict


def _graph_catalog(service: Any, workspace_id: str, user_id: str, held: set[str]) -> list[dict]:
    """The graphs ``user_id`` may assign to the workspace: the ones they administer
    (the level that may drop a graph: their workspace's own, or all for a platform
    administrator), plus what the workspace already holds. Sharing a graph is a
    right over the graph, so an administrator cannot hand their workspace another
    tenant's data by naming it."""
    store = service._get_catalog_store()
    uris = catalog_graphs(store)
    uris = uris & (graph_iam.allowed("DropGraph", uris, user=user_id) | held)
    owned = graph_iam.owned_by(workspace_id)
    labels = {
        str(row.g): str(row.label)
        for row in NexusCatalogStore(store).query(
            f"SELECT ?g ?label WHERE {{ GRAPH <{NEXUS_GRAPH}> {{ "
            "?g <http://www.w3.org/2000/01/rdf-schema#label> ?label . FILTER(isIRI(?g)) } }"
        )
    }
    return [
        {
            "id": uri,
            "name": labels.get(uri, uri.rsplit("/", 1)[-1]),
            "description": uri,
            "owned": uri in owned,
            "read_only": uri == SCHEMA_GRAPH,
            "available": True,
        }
        for uri in sorted(uris)
    ]


async def assignment_catalog(
    kind: Kind,
    workspace_id: str,
    ontologies: Any,
    graphs: Any,
    *,
    user_id: str,
    held: set[str],
) -> list[dict]:
    if kind == "graphs":
        return await asyncio.to_thread(_graph_catalog, graphs, workspace_id, user_id, held)
    items = await ontologies.list_ontology_files()
    identifiers = [
        normalize_ontology_ref(f"{item.module_name}:{Path(item.path).name}") for item in items
    ]
    counts = Counter(identifiers)
    return [
        {
            # Prefer deployment-independent identifiers; disambiguate duplicate names.
            "id": identifier if counts[identifier] == 1 else item.path,
            "path": item.path,
            "name": item.name,
            "description": item.module_name,
            "module": item.module_name,
            "available": True,
        }
        for item, identifier in zip(items, identifiers, strict=True)
    ]


def editor_payload(kind: Kind, saved, catalog: list[dict]) -> dict:
    data = dict(saved.data)
    if kind == "ontologies":
        refs = data["enabled"]
        enabled = [
            item["id"]
            for item in catalog
            if ontology_matches_seed(item.get("path", item["id"]), item["module"], refs)
        ]
        missing = [
            ref
            for ref in refs
            if not any(
                ontology_matches_seed(item.get("path", item["id"]), item["module"], [ref])
                for item in catalog
            )
        ]
        data["enabled"] = enabled + missing
    else:
        missing = sorted(
            (set(data["read"]) | set(data["write"])) - {item["id"] for item in catalog}
        )
    catalog = catalog + [
        {
            "id": ref,
            "name": ref,
            "description": "Unavailable in the current catalog",
            "available": False,
        }
        for ref in missing
    ]
    return {**asdict(saved), "data": data, "catalog": catalog}


async def _require_graph_rights(user: Any, current: dict, data: dict) -> None:
    """What the catalog check cannot see in a graph assignment.

    * ``read_all`` shares every graph of the workspace's organization with all its
      members, so turning it on is for platform administrators.
    * A graph the workspace only reads is still in the catalog (it holds it): moving
      it to ``write`` hands every writer of the workspace the right to change it,
      which takes the right to drop it, as sharing it for writing did.
    """
    if data["read_all"] and not current["read_all"]:
        if not await authz.allowed("ManageSystem", user=user):
            raise HTTPException(403, "Sharing every graph is for platform administrators.")
    new_writes = set(data["write"]) - set(current["write"])
    if new_writes:
        droppable = await asyncio.to_thread(
            graph_iam.allowed, "DropGraph", new_writes, user=user.id
        )
        if new_writes - droppable:
            raise HTTPException(
                403, "Writing a graph needs the right to drop it: ask the graph's administrators."
            )


def _held(kind: Kind, data: dict) -> set[str]:
    return set(data["read"]) | set(data["write"]) if kind == "graphs" else set()


# The editor payload carries the assignments and the catalog they are chosen
# from, so reading it is as much the administrators' as saving it is.
@router.get(
    "/{workspace_id}/resource-access/{kind}",
    dependencies=[guard("UpdateResourceAccess", id="kind")],
)
async def get_assignments(
    workspace_id: str,
    kind: Kind,
    user=Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
    ontologies: Any = Depends(get_ontology_service),
    graphs: Any = Depends(get_graph_service),
):
    saved = await load_resource_policy(db, workspace_id, kind)
    catalog = await assignment_catalog(
        kind, workspace_id, ontologies, graphs, user_id=user.id, held=_held(kind, saved.data)
    )
    return editor_payload(kind, saved, catalog)


@router.put(
    "/{workspace_id}/resource-access/{kind}",
    dependencies=[guard("UpdateResourceAccess", id="kind")],
)
async def save_assignments(
    workspace_id: str,
    kind: Kind,
    body: AssignmentUpdate,
    user=Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
    ontologies: Any = Depends(get_ontology_service),
    graphs: Any = Depends(get_graph_service),
):
    current = await load_resource_policy(db, workspace_id, kind)
    catalog = await assignment_catalog(
        kind, workspace_id, ontologies, graphs, user_id=user.id, held=_held(kind, current.data)
    )
    try:
        data = validate_policy(kind, body.policy)
        known = {item["id"] for item in catalog}
        if kind == "ontologies":
            added = set(data["enabled"]) - set(current.data["enabled"])
        else:
            added = _held(kind, data) - _held(kind, current.data)
        if added - known:
            raise ValueError("Select resources from the available catalog.")
        if kind == "graphs":
            await _require_graph_rights(user, current.data, data)
        saved = await ResourceAccessService(ResourcePolicyPostgres(db)).save(
            workspace_id,
            kind,
            data,
            body.revision,
            user.id,
        )
    except PolicyConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if kind == "graphs":
        # IAM enforces what was just saved: hold it for the workspace's members.
        await sync_workspace(db, workspace_id, store=graphs._get_catalog_store())
    return editor_payload(kind, saved, catalog)
