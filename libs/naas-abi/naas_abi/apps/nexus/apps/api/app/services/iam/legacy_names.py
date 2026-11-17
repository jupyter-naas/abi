"""The names of the grammar before container paths, for the start-up writes alone.

The moves that predate container paths (``feature_overrides``, ``role_features``,
``policy_tree``) still read and write ``abi:<org>:<workspace>`` scopes until the
move of the names (``container_names``) rewrites them, as do the move of the role
data of an install from before IAM (``bootstrap.migrate_role_data_before_names``)
and the configuration's seeds while that move waits (``core.org_seed``). Nothing
else imports this: every other name is built by ``names``.
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
