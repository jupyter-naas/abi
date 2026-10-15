"""Which repositories a Nexus workspace may use, and who may write them.

A repository id from a request is never trusted on its own (bug (b) of #44):

* it must belong to the request's workspace: IAM places it there (repositories
  created through Nexus are placed in their workspace), or it is the
  deployment's shared repository (``settings.coding_repo_id``, configured by
  the operator and kept on the platform);
* write access is granted only to a member (owner, admin or member, never a
  viewer) whom IAM allows ``source_control:UpsertFile`` on it, acting for the
  user; the grant itself (``AddCollaborator``, an admin action) is made as
  ``api``.

The workspace check stays in Nexus until #65 attaches role policies: until
then a Nexus user's side of a kernel check is the TRANSITIONAL
``builtin.transitional.user`` grant, which binds no repository to a workspace.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi_core.engine.call_context import (
    as_service_account,
    current_call_context,
    use_call_context,
)
from naas_abi_core.services.iam.guard import ServiceGuard
from naas_abi_core.services.iam.IAMPorts import IIAMService
from naas_abi_core.services.iam.names import NONE, encode_segment
from naas_abi_core.services.source_control.iam_catalog import CATALOG
from naas_abi_core.services.source_control.SourceControlPorts import Repo
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)

SERVICE = "source_control"
WRITE_ROLES = frozenset({"owner", "admin", "member"})
_SCOPE_ID = re.compile(r"^[a-z0-9_-]{1,64}$")


class AuthorizationUnavailable(RuntimeError):
    """IAM is not loaded: nothing is granted."""


class RepoNotInWorkspace(LookupError):
    """The repository does not exist for this workspace (the caller learns no more)."""


class RepoWriteDenied(PermissionError):
    """The caller sees the repository but may not write it."""


def canonical_repo_id(repo_id: str) -> str:
    return encode_segment(repo_id)


def belongs_to_workspace(iam: IIAMService, repo_id: str, workspace_id: str) -> bool:
    """Whether ``repo_id`` is this workspace's, or the shared deployment repository."""
    _, workspace = iam.resolve_placement(SERVICE, canonical_repo_id(repo_id))
    if workspace == workspace_id:
        return True
    return bool(settings.coding_repo_id) and (
        repo_id == settings.coding_repo_id and workspace == NONE
    )


def authorize_repo(
    iam: IIAMService | None,
    repo_id: str,
    workspace_id: str,
    role: str | None,
    *,
    write: bool,
) -> None:
    """Raise unless the request may use ``repo_id`` in ``workspace_id`` (and
    write it, with ``write``). Runs in the request's call context."""
    if iam is None:
        raise AuthorizationUnavailable("Authorization is unavailable")
    if not repo_id or not belongs_to_workspace(iam, repo_id, workspace_id):
        raise RepoNotInWorkspace(repo_id)
    if not write:
        return
    if role not in WRITE_ROLES:
        raise RepoWriteDenied("Viewers cannot write to repositories")
    name = ServiceGuard(CATALOG, lambda: iam).name("repo", repo_id)
    if not iam.authorize("source_control:UpsertFile", name).allowed:
        raise RepoWriteDenied(f"Writing {repo_id} is not allowed")


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


def place_in_workspace(
    iam: IIAMService, repo_id: str, workspace_id: str, organization_id: str | None
) -> None:
    """Place a repository Nexus created for a workspace there (RFC §4.4,
    explicit placement), with its branches and proposals."""
    org = organization_id if organization_id and _SCOPE_ID.match(organization_id) else NONE
    canonical = canonical_repo_id(repo_id)
    with as_service_account("api"):
        iam.put_placement(SERVICE, canonical, org, workspace_id)
        iam.put_placement(SERVICE, f"{canonical}/*", org, workspace_id)


def placement_workspace(iam: IIAMService, repo_id: str) -> Any:
    """The placement covering ``repo_id``, or None."""
    return iam.placement_of(SERVICE, canonical_repo_id(repo_id))
