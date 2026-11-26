"""``/api/workspaces/{workspace_id}/feature-access`` (Workspace settings › Features, and
Workspace Files in › Files) and ``/api/workspaces/{workspace_id}/offer`` (the agents, apps,
workflows and pipelines it offers, and the files it gives, in › Files): both edit
the workspace's allow-list, "<W> access".

Reading is reading the workspace's configuration (``GetWorkspaceConfiguration``, as
``/configuration``). Saving is IAM's own write made as the caller (``UpdatePolicy``
on "<W> access"), audited first and decided by IAM: the route declares it for the
matrix; the check is IAM's, inside the call.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (  # noqa: E501
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.port import FeatureChange
from naas_abi.apps.nexus.apps.api.app.services.feature_access.runtime import (
    get_feature_access_service,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import (
    FeatureAccessService,
    OfferChange,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.port import IamUnavailableError
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    PermissionDeniedError,
)
from pydantic import BaseModel, Field

router = APIRouter()
T = TypeVar("T")

# The IAM write a save makes as the caller.
WRITES = ("iam:UpdatePolicy",)


async def _call(call: Awaitable[T]) -> T:
    try:
        return await call
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(403, detail=str(exc)) from exc
    except IAMNotFoundError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except IAMConflictError as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except AuditUnavailable as exc:
        raise HTTPException(503, detail=f"No change made: {exc}") from exc
    except IamUnavailableError as exc:
        raise HTTPException(503, detail=str(exc)) from exc


Service = Depends(get_feature_access_service)
Signed = Depends(get_current_user_required)
# The policy a page edits: "<W> access" (the workspace's offer) when left out, or another
# policy the workspace owns (what it grants its holders, within the offer).
PolicyParam = Query(default=None, alias="policy", min_length=1, max_length=200)


class ChangeBody(BaseModel):
    feature: str = Field(min_length=1, max_length=64)
    # Only… is refused (``errors``): a feature is offered to the workspace or not.
    choice: Literal["everyone", "only", "nobody"]
    principals: list[str] = Field(default_factory=list, max_length=100)


class SaveBody(BaseModel):
    changes: list[ChangeBody] = Field(min_length=1, max_length=50)


@router.get(
    "/{workspace_id}/feature-access",
    dependencies=[
        guard(
            "GetWorkspaceConfiguration",
            denied="Only admins can view the workspace configuration",
        )
    ],
)
async def read_feature_access(
    workspace_id: str,
    user: User = Signed,
    service: FeatureAccessService = Service,
    policy_id: str | None = PolicyParam,
) -> dict[str, Any]:
    """Each enabled feature: who may use it here (Everyone, Only…, Nobody), the
    other policies naming it, whether the workspace offers it, and whether the caller
    may change it."""
    return await _call(service.read(user, workspace_id, policy_id))


@router.put(
    "/{workspace_id}/feature-access",
    dependencies=[declares(action) for action in WRITES],
)
async def save_feature_access(
    workspace_id: str,
    body: SaveBody,
    user: User = Signed,
    service: FeatureAccessService = Service,
    policy_id: str | None = PolicyParam,
) -> dict[str, Any]:
    """Several features at once, each as the caller; ``errors`` names those IAM (or
    the row's rules) refused, the others are saved. Answers the state after."""
    changes = [
        FeatureChange(c.feature, c.choice, tuple(dict.fromkeys(c.principals))) for c in body.changes
    ]
    return await _call(service.save(user, workspace_id, changes, policy_id))


class OfferChangeBody(BaseModel):
    kind: Literal["agents", "apps", "workflows", "pipelines"]
    module: str = Field(min_length=1, max_length=200)
    # ``*``: every item of the module (a shared module offered whole).
    name: str = Field(min_length=1, max_length=200)
    offered: bool


class OfferBody(BaseModel):
    changes: list[OfferChangeBody] = Field(min_length=1, max_length=100)


@router.get(
    "/{workspace_id}/offer",
    dependencies=[
        guard(
            "GetWorkspaceConfiguration",
            denied="Only admins can view the workspace configuration",
        )
    ],
)
async def read_workspace_offer(
    workspace_id: str,
    user: User = Signed,
    service: FeatureAccessService = Service,
    policy_id: str | None = PolicyParam,
) -> dict[str, Any]:
    """The agents, apps, workflows and pipelines the workspace offers (its
    allow-list, "<W> access"), by name or whole module; the files it gives outside it
    (``files``: a mode each, the modes the caller may choose) and what My Files is; its
    ontologies (``ontologies``: its refs and a row per file, whether the caller may
    assign it)."""
    return await _call(service.read_offer(user, workspace_id, policy_id))


class LevelsBody(BaseModel):
    # ``{group key: level}``: ``feature:graph``, ``service:triple_store``... (``access_levels``).
    changes: dict[str, Literal["none", "read", "write", "admin"]] = Field(
        min_length=1, max_length=100
    )


@router.get(
    "/{workspace_id}/access-levels",
    dependencies=[
        guard(
            "GetWorkspaceConfiguration",
            denied="Only admins can view the workspace configuration",
        )
    ],
)
async def read_access_levels(
    workspace_id: str,
    kind: Literal["feature", "service"] = Query(default="feature"),
    user: User = Signed,
    service: FeatureAccessService = Service,
    policy_id: str | None = PolicyParam,
) -> dict[str, Any]:
    """How far people go with each Nexus feature (``kind=feature``) or core service
    (``kind=service``) in the policy edited: a cap in "<W> access" (Denies), what another
    policy grants (Allows)."""
    return await _call(service.read_levels(user, workspace_id, kind, policy_id))


@router.put(
    "/{workspace_id}/access-levels",
    dependencies=[declares(action) for action in WRITES],
)
async def save_access_levels(
    workspace_id: str,
    body: LevelsBody,
    kind: Literal["feature", "service"] = Query(default="feature"),
    user: User = Signed,
    service: FeatureAccessService = Service,
    policy_id: str | None = PolicyParam,
) -> dict[str, Any]:
    """Set access levels in one write of the policy edited, as the caller (403 for a grant
    the caller does not hold, 422 for a level a group does not have). Answers the levels
    after."""
    return await _call(service.save_levels(user, workspace_id, kind, body.changes, policy_id))


class SearchSourcesBody(BaseModel):
    # ``{source id: offered}``: ``chat``, ``web.wikipedia``... (``search.sources``).
    changes: dict[str, bool] = Field(min_length=1, max_length=50)


@router.put(
    "/{workspace_id}/offer/search-sources",
    dependencies=[declares(action) for action in WRITES],
)
async def save_workspace_search_sources(
    workspace_id: str,
    body: SearchSourcesBody,
    user: User = Signed,
    service: FeatureAccessService = Service,
) -> dict[str, Any]:
    """Offer or stop offering search sources, in one write of "<W> access" as the
    caller (403 for a source the caller does not hold, 422 for one beyond the
    organization's offer). Answers the offer after."""
    return await _call(service.save_search_sources(user, workspace_id, body.changes))


class ModelsBody(BaseModel):
    """The chat models the workspace uses (``*``: every one) and its default model."""

    models: list[str] = Field(min_length=1, max_length=200)
    default: str | None = None


@router.put(
    "/{workspace_id}/offer/models",
    dependencies=[declares(action) for action in WRITES],
)
async def save_workspace_models(
    workspace_id: str,
    body: ModelsBody,
    user: User = Signed,
    service: FeatureAccessService = Service,
) -> dict[str, Any]:
    """The chat models the workspace uses and its default model, in one write of "<W>
    access" as the caller (403 for a model the caller does not hold, 422 for one beyond
    the organization's offer or a list with no default among it). Answers the offer
    after."""
    return await _call(service.set_models(user, workspace_id, body.models, body.default))


class FilesBody(BaseModel):
    """What the workspace gives its people outside it; a section left out is kept."""

    org_files: Literal["off", "read", "write"] | None = None
    platform_files: Literal["off", "read", "write"] | None = None
    system_files: Literal["off", "read"] | None = None


@router.put(
    "/{workspace_id}/offer/files",
    dependencies=[declares(action) for action in WRITES],
)
async def save_workspace_files(
    workspace_id: str,
    body: FilesBody,
    user: User = Signed,
    service: FeatureAccessService = Service,
) -> dict[str, Any]:
    """Give (or stop giving) Organization, Platform or System Files, in one write of
    "<W> access" as the caller (403 for a section the caller does not hold and the
    change widens; 422 for Organization Files in a workspace of no organization).
    Answers the offer after."""
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    return await _call(service.set_files(user, workspace_id, changes))


class OntologiesBody(BaseModel):
    # ``{catalog id: offered}``: ``core:bfo.ttl``... (the ``id`` of an ``ontologies`` row).
    changes: dict[str, bool] = Field(min_length=1, max_length=200)


@router.put(
    "/{workspace_id}/offer/ontologies",
    dependencies=[declares(action) for action in WRITES],
)
async def save_workspace_ontologies(
    workspace_id: str,
    body: OntologiesBody,
    user: User = Signed,
    service: FeatureAccessService = Service,
) -> dict[str, Any]:
    """Offer or stop offering ontology files, through the write Settings › Ontologies
    makes, as the caller (403 for a file the caller may not assign there, 422 for one
    of no file of the deployment). Answers the offer after."""
    return await _call(service.save_ontologies(user, workspace_id, body.changes))


@router.put(
    "/{workspace_id}/offer",
    dependencies=[declares(action) for action in WRITES],
)
async def save_workspace_offer(
    workspace_id: str,
    body: OfferBody,
    user: User = Signed,
    service: FeatureAccessService = Service,
    policy_id: str | None = PolicyParam,
) -> dict[str, Any]:
    """Offer or stop offering items, in one write of "<W> access" as the caller
    (403 for an item the caller does not hold, 422 for one beyond the
    organization's offer: nothing changes). Answers the offer after."""
    changes = [OfferChange(c.kind, c.module, c.name, c.offered) for c in body.changes]
    return await _call(service.save_offer(user, workspace_id, changes, policy_id))
