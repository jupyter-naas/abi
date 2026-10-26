"""Where Nexus's roles live in IAM: an organization's own roles
at ``abi:<org>:-``, a workspace's at ``abi:<org>:<workspace>``, each the
built-in policy ``builtin.<role>``. A workspace with no organization sits in
the reserved org ``_none``."""

from __future__ import annotations

NO_ORG = "_none"


def org_scope(org_id: str) -> str:
    return f"abi:{org_id}:-"


def workspace_scope(org_id: str | None, workspace_id: str) -> str:
    return f"abi:{org_id or NO_ORG}:{workspace_id}"


def role_policy(role: str) -> str:
    return f"builtin.{role}"
