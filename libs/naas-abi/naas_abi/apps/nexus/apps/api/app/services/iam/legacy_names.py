"""The names of the grammar before container paths, for the start-up moves alone.

The moves that predate container paths (``feature_overrides``, ``role_features``,
``policy_tree``) still read and write ``abi:<org>:<workspace>`` scopes until the
move of the names (``container_names``) rewrites them. Nothing else imports this:
every other name is built by ``names``.
"""

from __future__ import annotations

# The org of a workspace that had no organization, in the old grammar.
NO_ORG = "_none"


def org_scope(org_id: str) -> str:
    """An organization's own scope in the old grammar: ``abi:<org>:-``."""
    return f"abi:{org_id}:-"


def workspace_scope(org_id: str | None, workspace_id: str) -> str:
    """A workspace's scope in the old grammar: ``abi:<org>:<workspace>``."""
    return f"abi:{org_id or NO_ORG}:{workspace_id}"


__all__ = ["NO_ORG", "org_scope", "workspace_scope"]
