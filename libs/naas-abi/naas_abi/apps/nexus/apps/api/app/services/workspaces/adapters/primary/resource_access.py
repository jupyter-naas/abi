"""Admin assignment editor. Normal data APIs consume the same saved policies."""

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
    require_workspace_admin,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
    catalog_graphs,
    owned_graphs,
)
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


async def authorize_editor(workspace_id: str, user=Depends(get_current_user_required)):
    await require_workspace_admin(user.id, workspace_id)
    return user


def _graph_catalog(service: Any, workspace_id: str) -> list[dict]:
    store = service._get_catalog_store()
    uris = catalog_graphs(store)
    owned = owned_graphs(store, workspace_id)
    labels = {
        str(row.g): str(row.label)
        for row in store.query(
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
    kind: Kind, workspace_id: str, ontologies: Any, graphs: Any
) -> list[dict]:
    if kind == "graphs":
        return await asyncio.to_thread(_graph_catalog, graphs, workspace_id)
    items = await ontologies.list_ontology_files()
    identifiers = [
        normalize_ontology_ref(f"{item.module_name}:{Path(item.path).name}")
        for item in items
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
                ontology_matches_seed(
                    item.get("path", item["id"]), item["module"], [ref]
                )
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


@router.get("/{workspace_id}/resource-access/{kind}")
async def get_assignments(
    workspace_id: str,
    kind: Kind,
    _user=Depends(authorize_editor),
    db: AsyncSession = Depends(get_db),
    ontologies: Any = Depends(get_ontology_service),
    graphs: Any = Depends(get_graph_service),
):
    saved = await load_resource_policy(db, workspace_id, kind)
    catalog = await assignment_catalog(kind, workspace_id, ontologies, graphs)
    return editor_payload(kind, saved, catalog)


@router.put("/{workspace_id}/resource-access/{kind}")
async def save_assignments(
    workspace_id: str,
    kind: Kind,
    body: AssignmentUpdate,
    user=Depends(authorize_editor),
    db: AsyncSession = Depends(get_db),
    ontologies: Any = Depends(get_ontology_service),
    graphs: Any = Depends(get_graph_service),
):
    current = await load_resource_policy(db, workspace_id, kind)
    catalog = await assignment_catalog(kind, workspace_id, ontologies, graphs)
    try:
        data = validate_policy(kind, body.policy)
        known = {item["id"] for item in catalog}
        if kind == "ontologies":
            added = set(data["enabled"]) - set(current.data["enabled"])
        else:
            added = (set(data["read"]) | set(data["write"])) - (
                set(current.data["read"]) | set(current.data["write"])
            )
        if added - known:
            raise ValueError("Select resources from the available catalog.")
        saved = await ResourceAccessService(ResourcePolicyPostgres(db)).save(
            workspace_id,
            kind,
            data,
            body.revision,
            user.id,
            "admin",
        )
    except PolicyConflictError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return editor_payload(kind, saved, catalog)
