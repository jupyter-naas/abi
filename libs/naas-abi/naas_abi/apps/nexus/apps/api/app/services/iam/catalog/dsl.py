"""How a router declares what it authorizes (one module per router).

A module of this package exports ``TYPES`` (its resource types) and ``ACTIONS``
(its actions), built with ``rtype`` and ``action``. ``__init__`` aggregates them
into the ``nexus`` catalog, registered with IAM at startup.

Level is what the built-in roles are generated from:

* ``list`` and ``read``: viewers and up. A viewer reads everything it may see;
* ``write``: members and up. Every state change is at least ``write``;
* ``admin``: admins and up; ``owner_only``: owners alone (deleting the
  workspace or the organization).

``policy_only`` on a type: no role holds it, a policy grants it (features).
``container`` on a type: a step of the names of what it holds, registered with
IAM (organizations and workspaces); its ``creates`` action registers one, its
``deletes`` action deletes one. ``platform_companions`` on a container type: a
role attached at one brings the platform companions (workspaces).
A module may export ``PLATFORM_ACCESS``: its platform-level resources the
roles' platform companions reach (``PlatformAccess``, core's ``catalog.py``).

``feature`` is the ``FeatureKey`` whose ``UseFeature`` the action also needs
(see "Roles, features and platform types" in ``services/iam/AGENTS.md``), checked first by ``authz``.
"""

from __future__ import annotations

from dataclasses import dataclass

from naas_abi_core.services.iam.catalog import ActionSpec, Level, ResourceType
from naas_abi_core.services.iam.names import IdKind


@dataclass(frozen=True)
class NexusAction:
    spec: ActionSpec
    feature: str | None = None


def rtype(
    name: str,
    *,
    id: IdKind = "opaque",
    personal: bool = False,
    platform: bool = False,
    policy_only: bool = False,
    container: bool = False,
    platform_companions: bool = False,
    parents: tuple[str, ...] = (),
    description: str = "",
) -> ResourceType:
    return ResourceType(
        name=name,
        id=id,
        placement="platform" if platform else "placed",
        container=container,
        platform_companions=platform_companions,
        parents=parents,
        personal=personal,
        description=description,
        policy_only=policy_only,
    )


def action(
    name: str,
    level: Level,
    resource_type: str,
    *,
    feature: str | None = None,
    owner_only: bool = False,
    creates: bool = False,
    deletes: bool = False,
    description: str = "",
) -> NexusAction:
    return NexusAction(
        ActionSpec(
            name=name,
            level=level,
            resource_types=(resource_type,),
            creates=creates,
            description=description,
            owner_only=owner_only,
            deletes=deletes,
        ),
        feature=feature,
    )
