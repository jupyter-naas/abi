"""Which workspaces may use a Maps layer or basemap.

Two kinds of items carry a policy:

- deployment items (seeds, ``owner == DEPLOYMENT``): available to every
  workspace unless a grant narrows them to a list;
- custom items (records a workspace created): available to their owning
  workspace only, unless a grant shares them with a list of workspaces or all.

Built-in feeds and module graph layers have no policy (graph grants already
scope the latter). Hiding stays a per-workspace choice on top of this.
"""

from __future__ import annotations

from dataclasses import dataclass

KIND_LAYOUT = "layout"
KIND_BASEMAP = "basemap"
KINDS = frozenset({KIND_LAYOUT, KIND_BASEMAP})
DEPLOYMENT = ""


@dataclass(frozen=True)
class MapsGrant:
    kind: str
    item_id: str
    owner: str  # DEPLOYMENT or the owning workspace id
    # None: every workspace. Otherwise the workspaces it is shared with.
    workspace_ids: frozenset[str] | None

    def allows(self, workspace_id: str) -> bool:
        return (
            workspace_id == self.owner
            or self.workspace_ids is None
            or workspace_id in self.workspace_ids
        )


def default_grant(kind: str, item_id: str, owner: str) -> MapsGrant:
    """Policy when nothing is stored: deployment items everywhere, custom items at home."""
    return MapsGrant(kind, item_id, owner, None if owner == DEPLOYMENT else frozenset())


class MapsPermissionError(PermissionError):
    pass


class MapsPermissionValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors
