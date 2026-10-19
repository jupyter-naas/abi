"""Nexus's names in IAM: the scopes of orgs and workspaces, and resource names.

A workspace sits in its organization: ``abi:<org>:<workspace>``. A workspace
that belongs to none (a signup's personal workspace) sits in the reserved org
``_none``, so every workspace has a scope.
"""

from __future__ import annotations

from collections.abc import Sequence

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog import TYPES_BY_NAME
from naas_abi_core.services.iam.names import NONE, resource_name

SERVICE = "nexus"
# The org of a workspace that has no organization.
NO_ORG = "_none"
# Ids that name no workspace: an org's own scope is ``(org, -)``, ``*`` is every
# workspace, and ``_none`` is the org of those that have none. A path or query value
# of these never stands for a workspace.
RESERVED_WORKSPACE_IDS = frozenset({"", "-", "*", NO_ORG})


def org_scope(org_id: str) -> str:
    """Where an organization's own roles are attached: ``abi:<org>:-``."""
    return f"abi:{org_id}:{NONE}"


def workspace_scope(org_id: str | None, workspace_id: str) -> str:
    """Where a workspace's roles are attached: ``abi:<org>:<workspace>``."""
    return f"abi:{org_id or NO_ORG}:{workspace_id}"


def nexus_resource(
    type_name: str,
    *,
    org: str | None = None,
    workspace: str | None = None,
    id: str | Sequence[str] = (),
) -> str:
    """The canonical name of a Nexus resource.

    Platform-level with neither ``org`` nor ``workspace``; org-level with only
    ``org``; a workspace's with both.
    """
    resource_type = TYPES_BY_NAME[type_name]
    kind = resource_type.id
    if resource_type.placement == "platform":
        org, workspace = None, None
    return resource_name(
        SERVICE,
        type_name,
        id if kind != "singleton" else (),
        kind=kind,
        org=org or NONE,
        workspace=workspace or NONE,
    )
