"""Which workspaces may use a Maps layer or basemap.

Two kinds of items carry a policy:

- deployment items (seeds, ``owner == DEPLOYMENT``): available to every
  workspace unless a grant narrows them to a list;
- custom items (records a workspace created): available to their owning
  workspace only, unless a grant shares them with a list of workspaces or all.

Built-in feeds and module graph layers have no policy (graph grants already
scope the latter). Hiding stays a per-workspace choice on top of this.

Where a workspace's access policy is an allow-list, what it may use of the items it does
not own is its offer's (``MapsAssignment``, ``iam/given_maps``): ``maps_grants`` is what
a workspace whose policy is no allow-list yet still goes by.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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


@dataclass(frozen=True)
class MapsAssignment:
    """What one workspace may use of the Maps items it does not own, as the Maps part of
    its offer says (``iam/given_maps``): the deployment's items, every one of a kind (the
    ones added later too) or by id, less those it closes; and the items other workspaces
    share with it."""

    # Kinds of which every deployment item is given.
    every: frozenset[str] = field(default_factory=frozenset)
    # Deployment items given by id: (kind, id).
    platform: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    # Deployment items it closes, even when every one of their kind is given: (kind, id).
    closed: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    # Items of other workspaces shared with it: (kind, owning workspace, id).
    shared: frozenset[tuple[str, str, str]] = field(default_factory=frozenset)

    def gives_platform(self, kind: str, item_id: str) -> bool:
        """Whether the deployment item may be used: given (whole kind or by id), not closed."""
        given = kind in self.every or (kind, item_id) in self.platform
        return given and (kind, item_id) not in self.closed

    def shared_of(self, kind: str) -> frozenset[tuple[str, str]]:
        """(owning workspace, id) of the items of ``kind`` shared with it."""
        return frozenset((owner, item) for k, owner, item in self.shared if k == kind)


class MapsPermissionError(PermissionError):
    pass


class MapsPermissionValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors
