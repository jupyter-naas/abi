"""Where Nexus's roles live in IAM: an organization's own roles at its container
(``abi:nexus:organization/<org>``), a workspace's at the workspace's
(``…/nexus:workspace/<workspace>``, at the platform for a workspace in no
organization), each the built-in policy ``builtin.<role>``."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_container,
    workspace_container,
)


def org_scope(org_id: str) -> str:
    return org_container(org_id)


def workspace_scope(org_id: str | None, workspace_id: str) -> str:
    return workspace_container(org_id, workspace_id)


def role_policy(role: str) -> str:
    return f"builtin.{role}"
