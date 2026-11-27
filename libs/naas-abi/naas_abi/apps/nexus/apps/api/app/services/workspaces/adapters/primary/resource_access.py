"""Admin assignment editor. A workspace's graphs and ontologies are parts of its offer
("<W> access"), written as the caller through the offer service: the graphs it is given
(``iam/given_graphs``), which IAM gives its people and the graph APIs (through the
kernel) enforce, and the ontologies it offers, read by the ontology APIs. Each editor
offers only what the caller may assign, plus what the workspace already holds: a graph
they may drop, an ontology they may assign there (``AssignOntology`` in the workspace's
organization, ``services/ontology/ontology_access.py``). IAM refuses a graph given that
the caller does not hold (grant only what you hold)."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable
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
from naas_abi.apps.nexus.apps.api.app.services.feature_access.runtime import (
    get_feature_access_service,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary import graph_iam
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.nexus_catalog import (
    NexusCatalogStore,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.workspace_policy import (
    catalog_graphs,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import given_graphs
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ as authz
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import feature_exists
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import guard
from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology_access import (
    FEATURE as ONTOLOGY_FEATURE,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology_access import assignable_paths
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
    ResourcePolicy,
    validate_policy,
)
from naas_abi.apps.nexus.graph_policy_config import (
    NEXUS_GRAPH,
    SCHEMA_GRAPH,
    WorkspaceGraphPolicyConfig,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    PermissionDeniedError,
    RevisionConflictError,
)
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


async def _ontology_entries(ontologies: Any) -> list[dict]:
    """Every ontology file of the deployment, as the editor names it."""
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


async def assignment_catalog(
    kind: Kind,
    workspace_id: str,
    ontologies: Any,
    graphs: Any,
    *,
    user_id: str,
    held: set[str],
    enabled: list[str] | None = None,
    entries: list[dict] | None = None,
) -> list[dict]:
    """What ``user_id`` may assign to the workspace, plus what it holds already:
    ``held`` graphs, the ``enabled`` ontology refs. ``entries``: every ontology file,
    when the caller listed them already (``_ontology_entries``)."""
    if kind == "graphs":
        return await asyncio.to_thread(_graph_catalog, graphs, workspace_id, user_id, held)
    if entries is None:
        entries = await _ontology_entries(ontologies)
    assignable = await assignable_paths(user_id, workspace_id, [e["path"] for e in entries])
    return [
        entry
        for entry in entries
        if entry["path"] in assignable
        or ontology_matches_seed(entry["path"], entry["module"], enabled or [])
    ]


def offer_ontology_catalog(
    ontologies_of: Callable[[], Any],
) -> Callable[[Any, str], Awaitable[tuple[list[dict], set[str]] | None]]:
    """The catalog the offer's Configuration shows (``FeatureAccessService``'s
    ``ontology_catalog``): every ontology file, as this editor names them, and the ids
    the caller may assign to the workspace; None where the deployment has no ontology."""

    async def listing(user: Any, workspace_id: str) -> tuple[list[dict], set[str]] | None:
        if not feature_exists(ONTOLOGY_FEATURE):
            return None
        entries = await _ontology_entries(ontologies_of())
        user_id = getattr(user, "id", user)
        paths = await assignable_paths(user_id, workspace_id, [e["path"] for e in entries])
        return entries, {entry["id"] for entry in entries if entry["path"] in paths}

    return listing


async def _offered_ontologies(workspace_id: str) -> ResourcePolicy | None:
    """The workspace's ontologies as its offer names them ("<W> access",
    ``OfferOntologies``); None when its access policy is no allow-list yet (the stored
    list is still the one)."""
    container = await authz.container_of(workspace_id)
    offer = await authz.offer_of(container) if container else None
    if offer is None:
        return None
    return ResourcePolicy({"enabled": sorted(offer.ontologies)}, 1, None)


async def _offered_graphs(workspace_id: str) -> ResourcePolicy | None:
    """The workspace's graphs as its offer gives them ("<W> access", ``given_graphs``);
    None when its access policy is no allow-list yet (the stored assignments are still
    the ones)."""
    container = await authz.container_of(workspace_id)
    offer = await authz.offer_of(container) if container else None
    if offer is None:
        return None
    return ResourcePolicy(given_graphs.config_of(offer).model_dump(), 1, None)


async def _offered(workspace_id: str, kind: Kind) -> ResourcePolicy | None:
    if kind == "ontologies":
        return await _offered_ontologies(workspace_id)
    return await _offered_graphs(workspace_id)


async def _load(db: AsyncSession, workspace_id: str, kind: Kind) -> ResourcePolicy:
    if offered := await _offered(workspace_id, kind):
        return offered
    return await load_resource_policy(db, workspace_id, kind)


async def _save_graphs(user: Any, workspace_id: str, data: dict) -> ResourcePolicy:
    """Write the graphs ``data`` says into the workspace's offer, as the caller. A graph
    newly given is named as IAM placed it, which the caller must hold; the ones that stay
    keep their names; its own graphs are read for the ones it excludes."""
    config = WorkspaceGraphPolicyConfig.model_validate(data)

    def resolve() -> tuple[set[str], dict[str, list[str]]]:
        with as_service_account("api"):
            owned = graph_iam.owned_by(workspace_id)
            names = {
                iri: [graph_iam.graph_name(iri)] for iri in set(config.read) | set(config.write)
            }
        return owned, names

    owned, names = await asyncio.to_thread(resolve)
    offer = await get_feature_access_service().set_graphs(
        user,
        workspace_id,
        config,
        owned=owned,
        name_of=lambda iri: names.get(iri) or given_graphs.anywhere_names(iri),
    )
    return ResourcePolicy(given_graphs.config_of(offer).model_dump(), 1, None)


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
    """What IAM's held check does not see in a graph assignment: ``read_all`` gives
    every graph of the workspace's organization, the ones made later included, to all
    its people, so turning it on is for platform administrators. (Giving a graph to
    read or to write, IAM refuses to whoever does not hold it so: grant only what you
    hold; the catalog still offers only graphs the caller may drop.)"""
    if data["read_all"] and not current["read_all"]:
        if not await authz.allowed("ManageSystem", user=user):
            raise HTTPException(403, "Sharing every graph is for platform administrators.")


def _held(kind: Kind, data: dict) -> set[str]:
    return set(data["read"]) | set(data["write"]) if kind == "graphs" else set()


def _enabled(kind: Kind, data: dict) -> list[str]:
    return list(data["enabled"]) if kind == "ontologies" else []


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
    saved = await _load(db, workspace_id, kind)
    catalog = await assignment_catalog(
        kind,
        workspace_id,
        ontologies,
        graphs,
        user_id=user.id,
        held=_held(kind, saved.data),
        enabled=_enabled(kind, saved.data),
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
    offered = await _offered(workspace_id, kind)
    current = offered or await load_resource_policy(db, workspace_id, kind)
    # Every ontology file, listed once: the catalog, and the words of a refusal.
    entries = await _ontology_entries(ontologies) if kind == "ontologies" else None
    catalog = await assignment_catalog(
        kind,
        workspace_id,
        ontologies,
        graphs,
        user_id=user.id,
        held=_held(kind, current.data),
        enabled=_enabled(kind, current.data),
        entries=entries,
    )
    try:
        data = validate_policy(kind, body.policy)
        known = {item["id"] for item in catalog}
        if kind == "ontologies":
            added = set(data["enabled"]) - set(current.data["enabled"])
        else:
            added = _held(kind, data) - _held(kind, current.data)
        if kind == "ontologies" and added - known:
            # An ontology of the deployment the caller may not assign here.
            existing = {entry["id"] for entry in entries or []}
            refused = sorted((added - known) & existing)
            if refused:
                raise HTTPException(
                    403,
                    f"You may not assign {', '.join(refused)} to this workspace: "
                    "an administrator of its organization may (nexus:AssignOntology).",
                )
        if added - known:
            raise ValueError("Select resources from the available catalog.")
        if kind == "graphs":
            await _require_graph_rights(user, current.data, data)
        if offered is not None and kind == "graphs":
            # The workspace's offer: written as the caller, IAM's rules applying.
            saved = await _save_graphs(user, workspace_id, data)
        elif offered is not None:
            offer = await get_feature_access_service().set_ontologies(
                user, workspace_id, data["enabled"]
            )
            saved = ResourcePolicy({"enabled": sorted(offer.ontologies)}, 1, None)
        elif kind == "graphs":
            raise HTTPException(
                409,
                "This workspace's access policy is not an allow-list yet: its graphs are "
                "given there once the access migration has converted it.",
            )
        else:
            saved = await ResourceAccessService(ResourcePolicyPostgres(db)).save(
                workspace_id,
                kind,
                data,
                body.revision,
                user.id,
            )
    except PermissionDeniedError as exc:
        raise HTTPException(403, str(exc)) from exc
    except IAMNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (PolicyConflictError, RevisionConflictError, IAMConflictError) as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return editor_payload(kind, saved, catalog)
