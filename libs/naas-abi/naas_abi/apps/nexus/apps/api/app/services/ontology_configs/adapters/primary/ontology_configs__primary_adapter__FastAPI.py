"""Ontology configs FastAPI primary adapter.

Lists the full reference-ontology catalog discovered from loaded engine
modules, hydrates each row with the workspace's enable state, and exposes
a CRUD surface for per-workspace ontology configuration over HTTP. The
ontology counterpart of ``apps__primary_adapter__FastAPI``.

Routes
------
* ``GET    /api/ontology-configs/?workspace_id=…``      — catalog (with enable state)
* ``GET    /api/ontology-configs/{ws}``                 — list configs for workspace
* ``POST   /api/ontology-configs/{ws}``                 — create config
* ``GET    /api/ontology-configs/{ws}/{ontology_id:path}``    — get one config
* ``PATCH  /api/ontology-configs/{ws}/{ontology_id:path}``    — update / enable / disable
* ``DELETE /api/ontology-configs/{ws}/{ontology_id:path}``    — delete (reverts to default)

The catalog itself is not stored: it is rescanned from the engine on each
listing, and ``ontology_id`` is the stable ``<module>:<filename.ttl>`` key
derived from each file (see ``core.workspace_catalog_seed``).
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
    OntologyCatalogScope,
    normalize_ontology_ref,
    ontology_catalog_id,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.adapters.primary.ontology__primary_adapter__dependencies import (  # noqa: E501
    get_ontology_service,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology__schema import (
    OntologyServiceUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology.service import OntologyService
from naas_abi.apps.nexus.apps.api.app.services.ontology_configs.adapters.primary.ontology_configs__primary_adapter__dependencies import (  # noqa: E501
    get_ontology_configs_service,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology_configs.port import (
    OntologyCatalogItem,
    OntologyCatalogResponse,
    OntologyConfigCreate,
    OntologyConfigCreateInput,
    OntologyConfigRecord,
    OntologyConfigUpdate,
    OntologyConfigUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology_configs.scope import (
    build_ontology_catalog_scope,
)
from naas_abi.apps.nexus.apps.api.app.services.ontology_configs.service import (
    OntologyAlreadyConfiguredError,
    OntologyConfigsService,
)

router = APIRouter(dependencies=[Depends(get_current_user_required)])


class OntologyConfigsFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _serialize_record(record: OntologyConfigRecord) -> dict:
    data = asdict(record)
    data["created_at"] = record.created_at.isoformat()
    data["updated_at"] = record.updated_at.isoformat()
    return data


async def _catalog_items(
    ontology_service: OntologyService,
    scope: OntologyCatalogScope | None,
) -> list[OntologyCatalogItem]:
    """Full engine catalog, each row carrying its resolved enable state.

    ``scope=None`` (no workspace context) reports everything as disabled:
    enablement is per workspace, so there is nothing to resolve against.
    """
    try:
        # Always scan unfiltered: Settings must list disabled ontologies too.
        files = await ontology_service.list_ontology_files(catalog_scope=None)
    except OntologyServiceUnavailableError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return [
        OntologyCatalogItem(
            ontology_id=ontology_catalog_id(item.path, item.module_name),
            path=item.path,
            name=item.name,
            module_name=item.module_name,
            submodule_name=item.submodule_name,
            description=item.description,
            license=item.license,
            contributors=list(item.contributors or []),
            date=item.date,
            imports=list(item.imports or []),
            enabled=(
                scope.allows(item.path, item.module_name) if scope is not None else False
            ),
        )
        for item in files
    ]


async def _ensure_ontology_exists(
    ontology_id: str,
    ontology_service: OntologyService,
) -> None:
    """Reject ids that no loaded module ships, mirroring ``_ensure_app_exists``.

    Seed-written rows may use an alias form, so compare normalized ids.
    """
    normalized = normalize_ontology_ref(ontology_id)
    known = await _catalog_items(ontology_service, None)
    if normalized not in {item.ontology_id for item in known}:
        raise HTTPException(
            status_code=404, detail=f"Unknown ontology_id: {ontology_id}"
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", response_model=OntologyCatalogResponse)
async def list_ontology_catalog(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    ontology_service: OntologyService = Depends(get_ontology_service),
    configs_service: OntologyConfigsService = Depends(get_ontology_configs_service),
) -> OntologyCatalogResponse:
    """Return every reference ontology discovered from loaded modules.

    Unlike ``GET /api/ontology/ontologies`` this is *not* filtered to the
    enabled set — Settings needs the disabled rows to offer a toggle. When
    ``workspace_id`` is provided each row carries that workspace's enable
    state; ontologies without a stored record default to ``enabled=False``.
    """
    scope: OntologyCatalogScope | None = None
    if workspace_id:
        await require_workspace_access(current_user.id, workspace_id)
        scope = await build_ontology_catalog_scope(workspace_id, configs_service)

    items = await _catalog_items(ontology_service, scope)
    items.sort(key=lambda i: (i.module_name.lower(), i.name.lower()))
    return OntologyCatalogResponse(ontologies=items)


@router.get("/{workspace_id}")
async def list_ontology_configs(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    configs_service: OntologyConfigsService = Depends(get_ontology_configs_service),
) -> list[dict]:
    """List every stored ontology config for a workspace."""
    await require_workspace_access(current_user.id, workspace_id)
    records = await configs_service.list_ontology_configs(workspace_id)
    return [_serialize_record(r) for r in records]


@router.post("/{workspace_id}", status_code=201)
async def create_ontology_config(
    workspace_id: str,
    body: OntologyConfigCreate,
    current_user: User = Depends(get_current_user_required),
    ontology_service: OntologyService = Depends(get_ontology_service),
    configs_service: OntologyConfigsService = Depends(get_ontology_configs_service),
) -> dict:
    """Create a new ontology config row (errors if one already exists)."""
    await require_workspace_access(current_user.id, workspace_id)
    await _ensure_ontology_exists(body.ontology_id, ontology_service)
    try:
        record = await configs_service.create_ontology_config(
            OntologyConfigCreateInput(
                workspace_id=workspace_id,
                ontology_id=normalize_ontology_ref(body.ontology_id),
                enabled=body.enabled,
            )
        )
    except OntologyAlreadyConfiguredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _serialize_record(record)


@router.get("/{workspace_id}/{ontology_id:path}")
async def get_ontology_config(
    workspace_id: str,
    ontology_id: str,
    current_user: User = Depends(get_current_user_required),
    ontology_service: OntologyService = Depends(get_ontology_service),
    configs_service: OntologyConfigsService = Depends(get_ontology_configs_service),
) -> dict:
    """Get a single ontology config row."""
    await require_workspace_access(current_user.id, workspace_id)
    await _ensure_ontology_exists(ontology_id, ontology_service)
    record = await configs_service.get_ontology_config(
        workspace_id, normalize_ontology_ref(ontology_id)
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Ontology config not found")
    return _serialize_record(record)


@router.patch("/{workspace_id}/{ontology_id:path}")
async def update_ontology_config(
    workspace_id: str,
    ontology_id: str,
    updates: OntologyConfigUpdate,
    current_user: User = Depends(get_current_user_required),
    ontology_service: OntologyService = Depends(get_ontology_service),
    configs_service: OntologyConfigsService = Depends(get_ontology_configs_service),
) -> dict:
    """Update an ontology config (e.g. enable/disable).

    Idempotent: if no row exists yet, one is created with the supplied
    values. This lets the UI toggle simply call PATCH without a prior POST.
    """
    await require_workspace_access(current_user.id, workspace_id)
    await _ensure_ontology_exists(ontology_id, ontology_service)
    normalized = normalize_ontology_ref(ontology_id)

    record = await configs_service.update_ontology_config(
        workspace_id=workspace_id,
        ontology_id=normalized,
        updates=OntologyConfigUpdateInput(enabled=updates.enabled),
    )
    if record is None:
        # No existing row: create one. Missing fields fall back to defaults
        # (enabled=False), then we apply the requested update on top.
        enabled = False if updates.enabled is None else updates.enabled
        record = await configs_service.create_ontology_config(
            OntologyConfigCreateInput(
                workspace_id=workspace_id,
                ontology_id=normalized,
                enabled=enabled,
            )
        )
    return _serialize_record(record)


@router.delete("/{workspace_id}/{ontology_id:path}")
async def delete_ontology_config(
    workspace_id: str,
    ontology_id: str,
    current_user: User = Depends(get_current_user_required),
    ontology_service: OntologyService = Depends(get_ontology_service),
    configs_service: OntologyConfigsService = Depends(get_ontology_configs_service),
) -> dict[str, str]:
    """Delete the ontology config (reverts to the seed default, else disabled)."""
    await require_workspace_access(current_user.id, workspace_id)
    await _ensure_ontology_exists(ontology_id, ontology_service)
    deleted = await configs_service.delete_ontology_config(
        workspace_id, normalize_ontology_ref(ontology_id)
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Ontology config not found")
    return {"status": "deleted"}
