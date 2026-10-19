"""Which repositories and environments a Nexus workspace owns, and who may use them.

A repository id from a request is never trusted on its own (a repo id a client names):

* it must belong to the request's workspace: IAM places it there (repositories
  created through Nexus are placed in their workspace), or it is the
  deployment's shared repository (``settings.coding_repo_id``, configured by
  the operator and kept on the platform);
* what the caller may do with it is IAM's, acting for the user: reading is
  ``source_control:ListContents`` and writing ``source_control:UpsertFile`` on
  the repository as placed. There is no role list here: a workspace role
  reaches a repository only once the repository is placed in that workspace;
* the grant itself (``AddCollaborator``, an admin action) is made as ``api``,
  only after that check passed.

An environment is the same: ``environment/<owner>/<id>``, placed in the
workspace it was provisioned for, and personal to its owner.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import replace

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.models import CodingEnvironmentModel, WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS, UnknownUserError
from naas_abi.apps.nexus.apps.api.app.services.iam.placements import (
    Placement,
    placement_source,
)
from naas_abi_core import logger
from naas_abi_core.engine.call_context import (
    as_service_account,
    current_call_context,
    use_call_context,
)
from naas_abi_core.services.iam.guard import ServiceGuard
from naas_abi_core.services.iam.IAMPorts import IIAMService
from naas_abi_core.services.iam.names import NONE, encode_id, encode_segment
from naas_abi_core.services.source_control.iam_catalog import CATALOG
from naas_abi_core.services.source_control.SourceControlPorts import Repo
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
    repo_key,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

SERVICE = "source_control"
ENVIRONMENT_SERVICE = "coding_environment"
_SCOPE_ID = re.compile(r"^[a-z0-9_-]{1,64}$")
_REPO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")


class AuthorizationUnavailable(RuntimeError):
    """IAM is not loaded: nothing is granted."""


class RepoNotInWorkspace(LookupError):
    """The repository does not exist for this workspace (the caller learns no more)."""


class RepoAccessDenied(PermissionError):
    """The caller sees the repository but IAM does not let them do this to it."""


class EnvironmentNotInWorkspace(LookupError):
    """The environment was provisioned for another workspace."""


def canonical_repo_id(repo_id: str) -> str:
    """The id IAM places a repository under: lowercase, as the forge looks it up."""
    return encode_segment(repo_key(repo_id))


def belongs_to_workspace(iam: IIAMService, repo_id: str, workspace_id: str) -> bool:
    """Whether ``repo_id`` is this workspace's, or the shared deployment repository."""
    _, workspace = iam.resolve_placement(SERVICE, canonical_repo_id(repo_id))
    if workspace == workspace_id:
        return True
    return bool(settings.coding_repo_id) and (
        repo_key(repo_id) == repo_key(settings.coding_repo_id) and workspace == NONE
    )


def authorize_repo(
    iam: IIAMService | None, repo_id: str, workspace_id: str, *, write: bool
) -> None:
    """Raise unless the request may use ``repo_id`` in ``workspace_id`` (and
    write it, with ``write``): the workspace must own it and IAM must allow the
    caller. Runs in the request's call context."""
    if iam is None:
        raise AuthorizationUnavailable("Authorization is unavailable")
    if not repo_id or not belongs_to_workspace(iam, repo_id, workspace_id):
        raise RepoNotInWorkspace(repo_id)
    name = ServiceGuard(CATALOG, lambda: iam).name("repo", repo_key(repo_id))
    action = "source_control:UpsertFile" if write else "source_control:ListContents"
    decision = iam.authorize(action, name)
    if decision.allowed:
        return
    if not decision.visible:
        raise RepoNotInWorkspace(repo_id)
    verb = "Writing" if write else "Reading"
    raise RepoAccessDenied(f"{verb} {repo_id} is not allowed")


def authorize_environment(iam: IIAMService | None, environment_id: str, workspace_id: str) -> None:
    """Raise unless ``environment_id`` was provisioned for ``workspace_id``.

    The owner is the call's user: an environment of someone else is not found
    by the kernel (it names ``environment/<owner>/<id>`` from its own records),
    and one placed in another workspace is not this workspace's. One that is
    not placed anywhere is left to the kernel, which no workspace role reaches.
    """
    if iam is None:
        raise AuthorizationUnavailable("Authorization is unavailable")
    owner = current_call_context().user
    _, placed = iam.resolve_placement(
        ENVIRONMENT_SERVICE,
        encode_id([owner.id if owner else NONE, environment_id], "path"),
    )
    if placed not in (NONE, workspace_id):
        raise EnvironmentNotInWorkspace(environment_id)


def grant_write(sc: SourceControlService, repo_id: str, username: str) -> None:
    """Make ``username`` a writer of ``repo_id``: an admin action, done as ``api``
    once ``authorize_repo(..., write=True)`` passed."""
    with as_service_account("api"):
        sc.add_collaborator(repo_id=repo_id, username=username, permission="write")


def ensure_shared_repo(sc: SourceControlService, *, owner: str, name: str) -> Repo:
    """Ensure the deployment's shared repository: a platform container, so it is
    ensured with no target workspace, whatever the request's workspace."""
    context = current_call_context()
    with use_call_context(replace(context, workspace_id=None)):
        return sc.ensure_repo(owner=owner, name=name)


class RepoNameTaken(LookupError):
    """The repository name is held by another repository or placement."""


def place_created_repo(
    iam: IIAMService, repo: Repo, workspace_id: str, organization_id: str | None
) -> None:
    """Make sure a repository this request just created (``create_repo``, in the
    workspace's call context) is placed in its workspace, with its branches and
    proposals (RFC §4.4).

    The kernel's create rule places it when IAM knows the workspace. When it
    could not, the repository sits on the platform and is placed here, as
    ``api``: it replaces only the platform placement the create recorded for this
    very repository; any other placement means the name is not this request's to
    place, and nothing is changed.
    """
    canonical = canonical_repo_id(f"{repo.owner}/{repo.name}")
    current = iam.placement_of(SERVICE, canonical)
    if current is not None and current.workspace == workspace_id:
        return
    if current is not None and (
        current.id_key != canonical or (current.org, current.workspace) != (NONE, NONE)
    ):
        raise RepoNameTaken(canonical)
    org = organization_id if organization_id and _SCOPE_ID.match(organization_id) else NONE
    with as_service_account("api"):
        iam.put_placement(SERVICE, canonical, org, workspace_id)
        iam.put_placement(SERVICE, f"{canonical}/*", org, workspace_id)


# -- what already exists ---------------------------------------------------------------


def _on_platform(iam: IIAMService, service: str, id_key: str) -> bool:
    """Whether nothing places this resource in a workspace yet."""
    current = iam.placement_of(service, id_key)
    return current is None or (current.org, current.workspace) == (NONE, NONE)


def _platform_keys(service: str, keys: list[str]) -> set[str]:
    try:
        iam = runtime.iam()
    except runtime.IAMUnavailableError:
        return set()
    with as_service_account("api"):
        return {key for key in keys if _on_platform(iam, service, key)}


@placement_source
async def workspace_repositories(db: AsyncSession) -> list[Placement]:
    """The repositories Nexus recorded for a workspace (its default repository,
    the repository of each of its environments) that nothing places yet.

    A recorded repository id was once a client's word (bug (b)), so only a
    repository claimed by exactly one workspace and still on the platform is
    placed; one claimed by several is left alone and logged. The deployment's
    shared repository belongs to no workspace.
    """
    claims: dict[str, tuple[str, set[str]]] = defaultdict(lambda: ("", set()))
    defaults = await db.execute(
        select(WorkspaceModel.id, WorkspaceModel.coding_default_repo_id).where(
            WorkspaceModel.coding_default_repo_id.is_not(None)
        )
    )
    environments = await db.execute(
        select(CodingEnvironmentModel.workspace_id, CodingEnvironmentModel.repo_id).where(
            CodingEnvironmentModel.repo_id.is_not(None)
        )
    )
    rows = [*defaults.all(), *environments.all()]
    for workspace, repo_id in rows:
        if not repo_id or not _REPO_ID.match(repo_id) or not workspace:
            continue
        if settings.coding_repo_id and repo_key(repo_id) == repo_key(settings.coding_repo_id):
            continue
        _, workspaces = claims[repo_key(repo_id)]
        claims[repo_key(repo_id)] = (repo_id, workspaces | {workspace})
    keys = {key: encode_segment(key) for key in claims}
    free = await run_in_threadpool(_platform_keys, SERVICE, list(keys.values()))
    placements: list[Placement] = []
    for key, (repo_id, workspaces) in claims.items():
        if keys[key] not in free:
            continue
        if len(workspaces) != 1:
            logger.warning(
                f"Repository {repo_id} is claimed by several workspaces "
                f"({', '.join(sorted(workspaces))}): left on the platform"
            )
            continue
        (workspace,) = workspaces
        placements.append(Placement(SERVICE, key, workspace, kind="opaque"))
        placements.append(Placement(SERVICE, (key,), workspace, prefix=True))
    return placements


@placement_source
async def workspace_environments(db: AsyncSession) -> list[Placement]:
    """The environments Nexus provisioned for a workspace, placed in it (an
    environment is ``environment/<owner principal>/<id>``)."""
    rows = (
        await db.execute(
            select(
                CodingEnvironmentModel.id,
                CodingEnvironmentModel.workspace_id,
                CodingEnvironmentModel.user_id,
            )
        )
    ).all()
    owners: dict[str, str] = {}
    found: list[Placement] = []
    for environment_id, workspace, user_id in rows:
        if not (environment_id and workspace and user_id):
            continue
        if user_id not in owners:
            try:
                owners[user_id] = await MEMBERSHIPS.principal_id(user_id)
            except UnknownUserError:
                owners[user_id] = ""  # an environment of a user who is gone: nobody's to place
        if owners[user_id]:
            found.append(
                Placement(ENVIRONMENT_SERVICE, (owners[user_id], environment_id), workspace)
            )
    free = await run_in_threadpool(
        _platform_keys,
        ENVIRONMENT_SERVICE,
        [p.id_key() for p in found],
    )
    return [p for p in found if p.id_key() in free]
